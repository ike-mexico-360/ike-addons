# import re
import logging
import requests
# from urllib.parse import urlparse, parse_qs
from collections import defaultdict
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
from markupsafe import Markup
from werkzeug.urls import url_encode

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(selection_add=[
        ('to_consolidate', 'To Consolidate'),
        ('consolidated', 'Consolidated'),
        ('purchase',),  # Ancla de posición
    ])
    x_event_id = fields.Many2one('ike.event', string='Event', ondelete='set null')
    x_sub_service_id = fields.Many2one('product.product', string='Subservice')
    x_nu_user_id = fields.Many2one('custom.nus', string='NU User', help="Technical: NU linked to the event of the purchase order")
    x_membership_plan_id = fields.Many2one('custom.membership.plan', string='Membership Plan', help="Technical: Membership Plan linked to the event of the purchase order")
    x_dispute_state = fields.Selection([
        ('none', 'No Dispute'),
        ('open', 'Open'),
        ('submitted', 'Submitted'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ], string='Dispute State', default='none')
    x_dispute_approved = fields.Boolean(string='Dispute Approved', default=False)
    x_ref_sap = fields.Char(string='SAP Reference')
    x_sap_reference_received = fields.Boolean(string='SAP Reference Received', default=False)
    x_sap_connection_error_message = fields.Char(string='SAP Connection Error Message')
    x_dispute_iteration_count = fields.Integer(
        string='Dispute Iteration Count', default=0,
        help="Technical: The number of times the order has been send dispute.")
    x_event_public_id = fields.Many2one(
        'ike.event.public',
        string='Event Public',
        compute='_compute_x_event_public_id',
        store=True
    )

    @api.depends('x_event_id')
    def _compute_x_event_public_id(self):
        for record in self:
            if record.x_event_id:
                record.x_event_public_id = record.sudo().x_event_id.id
            else:
                record.x_event_public_id = False

    # Add tracking native field
    order_line = fields.One2many(tracking=True)

    x_require_change_reason = fields.Boolean(
        string='Require change reason',
        default=False,
        store=False,  # No necesita persistir
    )
    x_change_comments = fields.Text(
        string='Change comments',
        store=False,
    )

    amount_untaxed_dispute = fields.Monetary(string='Untaxed Amount Dispute', store=True, readonly=True, compute='_x_amount_all_dispute', tracking=True)
    amount_untaxed_approved = fields.Monetary(string='Untaxed Amount Approved', store=True, readonly=True, compute='_x_amount_all_approved', tracking=True)
    amount_untaxed_event = fields.Monetary(string='Untaxed Amount Event', store=True, readonly=True, compute='_x_amount_all_event', tracking=True)

    @api.onchange('order_line')
    def _onchange_order_line_check_reason(self):
        self.ensure_one()
        if not self.x_event_id:
            return

        watched_fields = {
            'price_unit', 'product_qty',
            'x_price_unit_dispute', 'x_product_qty_dispute',
            'x_price_unit_approved', 'x_product_qty_approved'
        }

        for line in self.order_line:
            # _origin tiene los valores originales antes del cambio
            if line._origin.id:  # Línea existente modificada
                for field in watched_fields:
                    if line[field] != line._origin[field]:
                        self.x_require_change_reason = True
                        return
            else:  # Línea nueva
                self.x_require_change_reason = True
                return

        # Verificar líneas eliminadas
        original_ids = self._origin.order_line.ids
        current_ids = self.order_line.filtered('id').ids
        if set(original_ids) - set(current_ids):
            self.x_require_change_reason = True
            return

        self.x_require_change_reason = False

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Si es creado desde eventos
        if self._context.get('ike_event_purchase'):
            for purchase_id in res:
                purchase_id._x_ike_check_automatic_rfq()
        return res

    def write(self, vals):
        comments = vals.pop('x_change_comments', None)
        result = super().write(vals)
        if comments:
            for rec in self.filtered('x_event_id'):
                rec.sudo().message_post(
                    body=Markup(f"<strong style='font-weight: 500;'>Cambio en líneas de compra</strong><br/>{comments}"),
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
        return result

    # - - - - - - - - - - - - #
    #    Dispute workflow     #
    # - - - - - - - - - - - - #

    # Depends methods
    @api.depends('order_line.x_price_subtotal_dispute')
    def _x_amount_all_dispute(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            order.amount_untaxed_dispute = sum(order_lines.mapped('x_price_subtotal_dispute'))

    @api.depends('order_line.x_price_subtotal_approved')
    def _x_amount_all_approved(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            order.amount_untaxed_approved = sum(order_lines.mapped('x_price_subtotal_approved'))

    @api.depends('order_line.x_price_subtotal_event')
    def _x_amount_all_event(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            order.amount_untaxed_event = sum(order_lines.mapped('x_price_subtotal_event'))

    # Auxiliar methods
    def _x_action_start_dispute(self):
        """ Proveedor no acepta propuesta de comprador, se inicia disputa desde el portal """
        self.ensure_one()

        if self.state not in ['sent']:
            raise UserError(_('A dispute can only be opened on orders in Sent state.'))

        if self.x_dispute_state == 'open':
            raise UserError(_('This order already has an open dispute.'))

        self.write({'x_dispute_state': 'open'})

    def _x_start_sh_helpdesk_ticket(self):
        """ Se crea el ticket donde se dejará el log de los cambios para la disputa """
        # ToDo: Validar que el ticket no esté cerrado, si está cerrado, se crea otro
        if self.partner_id:
            HelpdeskTicket = self.env['sh.helpdesk.ticket'].sudo()
            ticket_ids = HelpdeskTicket.search([
                ('partner_id', '=', self.partner_id.id),
            ])
            ticket_id = ticket_ids.filtered(lambda x: self.id in x.sh_purchase_order_ids.ids)
            if not ticket_id:
                HelpdeskTicket.create({
                    'state': 'customer_replied',
                    'partner_id': self.partner_id.id,
                    'sh_purchase_order_ids': [(6, 0, [self.id])],
                    'state': 'customer_replied',
                })
            # Cuando se mande la disputa, marcar en el ticket como "Proveedor respondió"
            ticket_id.write({'state': 'customer_replied'})

    def x_get_dispute_url(self, confirm_type=None):
        """Create url for confirm or reject purchase dispute
        """
        if confirm_type in ['accept', 'decline']:
            param = url_encode({
                'dispute': confirm_type,
            })
            return f"/my/purchase/{self.id}/dispute?access_token={self._portal_ensure_token()}&{param}"
        return self.get_portal_url()

    def x_portal_action_accept_prices(self):
        """El acepta los pecios tal cual están portal."""
        self.ensure_one()

        if self.x_dispute_state not in ('none', 'resolved'):
            raise UserError(_('There is a dispute on this order.'))

        # Ejecutar asignación solo cuando la iteración sea la primera
        if self.x_dispute_iteration_count == 0:
            for line in self.order_line:
                line.write({
                    'x_price_unit_approved': line.price_unit,
                    'x_product_qty_approved': line.product_qty,
                })
        else:
            for line in self.order_line:
                line.write({
                    'price_unit': line.x_price_unit_approved,
                    'product_qty': line.x_product_qty_approved,
                })

        # Cerrar tickets
        for ticket in self.sh_purchase_ticket_ids:
            ticket.sudo().with_context(is_portal=True).action_done()

        self.x_action_start_consolidation()

    def x_action_submit_dispute(self):
        """El proveedor confirma su propuesta de disputa desde el portal."""
        self.ensure_one()
        self.sudo()._x_action_start_dispute()

        if self.x_dispute_state != 'open':
            raise UserError(_('There is no open dispute on this order.'))

        disputed_lines = self.order_line.filtered(
            lambda line: line.x_price_unit_dispute > 0 or line.x_product_qty_dispute > 0
        )
        if not disputed_lines:
            raise UserError(_('You must propose at least one new price or quantity before submitting.'))

        if self.x_dispute_state == 'submitted':
            raise UserError(_('This order already has a dispute submitted.'))

        self.sudo()._x_start_sh_helpdesk_ticket()
        # template = self.sudo().env.ref('ike_event_purchase.ike_event_purchase_proposal_dispute_ticket')
        # ticket_ids_sudo = self.sudo().sh_purchase_ticket_ids
        # for ticket in ticket_ids_sudo:
        #     template.sudo().with_context(dict(self._context, actual_order=self.id)).send_mail(ticket.id, force_send=True)
        #     self.sudo().message_post(
        #         body=_('The supplier has submitted their dispute proposal on ticket #%s.') % ticket.name,
        #         message_type='notification',
        #         subtype_xmlid='mail.mt_note',
        #     )
        self.x_dispute_state = 'submitted'

    def x_action_approve_dispute(self):
        """ Comprador acepta la propuesta del proveedor desde el ticket. """
        self.ensure_one()
        for line in self.order_line:
            vals = {}
            if line.x_price_unit_dispute:
                vals.update({
                    # Se envía el valor disputado al campo original de la compra y al aprobado
                    'price_unit': line.x_price_unit_dispute,
                    'x_price_unit_approved': line.x_price_unit_dispute,
                })
            if line.x_product_qty_dispute:
                vals.update({
                    # Se envía el valor disputado al campo original de la compra y al aprobado
                    'product_qty': line.x_product_qty_dispute,
                    'x_product_qty_approved': line.x_product_qty_dispute,
                })
            if vals:
                line.write(vals)
        self.write({
            'x_dispute_state': 'resolved',
            'x_dispute_approved': True,
        })
        self.message_post(
            body=_('Dispute approved. Approved values have been recorded.'),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        ticket_ids_sudo = self.sudo().sh_purchase_ticket_ids
        for ticket in ticket_ids_sudo:
            ticket.message_post(
                body=_('Dispute approved. Approved values have been recorded.'),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        # if self.partner_id.x_has_consolidation:
        #     self.x_action_consolidate()
        self.x_action_start_consolidation()

    def x_action_send_new_values_rfq(self):
        """ Send new values to RFQ. Show again in portal """
        self.ensure_one()
        if self.x_dispute_state != 'submitted':
            raise UserError(_('There is no submitted dispute on this order.'))
        # Validar que no hay campos aprobados en 0
        # empty_vals = []
        # for line in self.order_line:
        #     if line.x_price_unit_approved == 0 or line.x_product_qty_approved == 0:
        #         empty_vals.append(line.id)
        # if empty_vals:
        #     raise UserError(_('There are zero approved values on lines.'))
        self.write({'x_dispute_state': 'resolved'})

    def x_action_reject_dispute(self):
        """ Comprador rechaza la propuesta, se limpian los campos dispute. """
        self.ensure_one()

        if self.x_dispute_state != 'submitted':
            raise UserError(_('There is no submitted dispute on this order.'))

        lines_summary = []
        for line in self.order_line.filtered(
            lambda line: line.x_price_unit_dispute > 0 or line.x_product_qty_dispute > 0
        ):
            lines_summary.append(
                f"<li><b>{line.product_id.display_name}</b>: "
                f"{_('Qty')}: {line.x_product_qty_dispute} → {line.product_qty} | "
                f"{_('Price')}: {line.x_price_unit_dispute} → {line.price_unit}"
                f"</li>"
            )

        body = _('Dispute rejected. The values change has been reverted.')
        if lines_summary:
            body += '<ul>' + ''.join(lines_summary) + '</ul>'

        for line in self.order_line:
            line.write({
                'x_price_unit_dispute': line.price_unit,
                'x_product_qty_dispute': line.product_qty,
            })

        self.write({'x_dispute_state': 'rejected'})

        self.message_post(
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    def action_rfq_send_one_step(self):
        """Sends the RFQ email by executing the mail composer wizard."""
        self.ensure_one()
        if self.state in ['draft', 'sent'] and not self.env.user.has_group('custom_master_catalog.custom_group_event_coordinator'):
            action_data = self.action_rfq_send()
            ctx = action_data.get('context', {})
            ir_model_data = self.env['ir.model.data']
            template_id = ir_model_data._xmlid_lookup('purchase.email_template_edi_purchase')[1]
            compose_wizard = self.env['mail.compose.message'].with_context(ctx).create({
                'composition_mode': 'comment',
                'model': 'purchase.order',
                'res_ids': self.ids,
                'template_id': template_id,
            })
            compose_wizard.action_send_mail()

    def x_action_close_ticket(self):
        """Close ticket"""
        self.ensure_one()
        for ticket in self.sh_purchase_ticket_ids:
            ticket.sudo().action_closed()

    # - - - - - - - - - - - - - #
    #      Consolidation        #
    # - - - - - - - - - - - - - #
    def x_action_consolidate(self):
        self._x_validate_orders_for_consolidation()

        rfqs = self.filtered(lambda po: po.state == 'to_consolidate')
        if not rfqs:
            return self._x_get_consolidation_notification(
                notification_type='warning',
                message=_('There are no purchase orders to consolidate.')
            )

        try:
            new_po_vals, original_pos = self._x_prepare_consolidated_purchase_orders(rfqs)

            if not new_po_vals:
                return self._x_get_consolidation_notification(
                    notification_type='warning',
                    message=_('No consolidated purchase orders could be generated.')
                )

            new_po_ids = self.env['purchase.order'].create(new_po_vals)
            original_pos.write({'state': 'consolidated'})
            new_po_ids.button_confirm()

            try:
                new_po_ids.x_syncronize_po_with_sap()
            except Exception:
                _logger.exception(
                    "Error synchronizing consolidated purchase orders with SAP. PO ids: %s",
                    new_po_ids.ids,
                )

        except Exception:
            _logger.exception(
                "Error consolidating purchase orders. Selected PO ids: %s",
                self.ids,
            )
            return self._x_get_consolidation_notification(
                notification_type='error',
                message=_('Error consolidating purchase orders')
            )

        return self._x_get_consolidation_notification(
            notification_type='success',
            message=_('Purchase orders consolidated')
        )

    def _x_validate_orders_for_consolidation(self):
        disputed_pos = self.filtered(lambda po: po.x_dispute_state in ('open', 'submitted'))
        if disputed_pos:
            raise UserError(_(
                'The following orders have an open or submitted dispute and cannot be consolidated:\n%s'
            ) % '\n'.join(disputed_pos.mapped('name')))

    def _x_prepare_consolidated_purchase_orders(self, rfqs):
        grouped_rfqs = self._x_group_rfqs_by_partner_and_subservice(rfqs)

        new_po_vals = []
        original_pos = self.env['purchase.order']

        for group_key, partner_rfqs in grouped_rfqs.items():
            grouped_concept_lines = self._x_group_lines_by_sap_concept(partner_rfqs)

            partner_new_po_vals, partner_original_pos = self._x_build_partner_consolidated_pos(
                grouped_concept_lines,
            )

            new_po_vals.extend(partner_new_po_vals)
            original_pos |= partner_original_pos

        return new_po_vals, original_pos

    def _x_group_rfqs_by_partner_and_subservice(self, rfqs):
        grouped_ids = defaultdict(list)

        for rfq in rfqs:
            grouped_ids[(rfq.partner_id.id, rfq.x_nu_user_id.id, rfq.x_sub_service_id.id)].append(rfq.id)

        return {
            key: self.env['purchase.order'].browse(rfq_ids)
            for key, rfq_ids in grouped_ids.items()
        }

    def _x_group_lines_by_sap_concept(self, rfqs):
        grouped_concept_lines = defaultdict(list)
        concept_line_cache = {}

        for rfq in rfqs:
            membership_plan_id = rfq.x_membership_plan_id.id
            sub_service_id = rfq.x_sub_service_id.id
            cache_key = (sub_service_id, membership_plan_id)

            if cache_key not in concept_line_cache:
                concept_line = self.env['custom.membership.plan.product.line'].search([
                    ('sub_service_ids', 'in', [sub_service_id]),
                    ('membership_plan_id', '=', membership_plan_id),
                ], limit=1)
                concept_line_cache[cache_key] = concept_line
            concept_line = concept_line_cache[cache_key]

            if not concept_line:
                _logger.warning(
                    "No concept line found for RFQ id=%s, sub_service_id=%s, membership_plan_id=%s",
                    rfq.id,
                    sub_service_id,
                    membership_plan_id,
                )
                continue

            sap_key = (concept_line.sap_id_outgoing, concept_line.product_description_po)

            grouped_concept_lines[sap_key].append({
                'rfq': rfq,
                'subtotal': sum(rfq.order_line.mapped('price_subtotal')),
                'concept_line': concept_line,
                'event': rfq.x_event_id.id,
            })

        return grouped_concept_lines

    def _x_build_partner_consolidated_pos(self, grouped_concept_lines):
        new_po_vals = []
        original_pos = self.env['purchase.order']

        for _sap_key, concept_lines in grouped_concept_lines.items():
            first_order = concept_lines[0]['rfq']
            origin_names = []
            order_lines = []

            for item in concept_lines:
                rfq = item['rfq']
                subtotal = item['subtotal']
                concept_line = item['concept_line']
                event_id = item['event']
                product_id = concept_line.sub_service_ids[:1].id

                if not product_id:
                    _logger.warning(
                        "Concept line id=%s has no product configured in sub_service_ids. RFQ id=%s",
                        concept_line.id,
                        rfq.id,
                    )
                    continue

                if rfq.name not in origin_names:
                    origin_names.append(rfq.name)

                order_lines.append(Command.create({
                    'name': "[%s] %s - %s" % (
                        concept_line.sap_id_outgoing,
                        concept_line.product_description_po,
                        rfq.name,
                    ),
                    'product_id': product_id,
                    'product_qty': 1,
                    'price_unit': subtotal,
                    'x_concept_line_id': concept_line.id,
                    'x_parent_event_id': event_id,
                }))

                original_pos |= rfq

            if not order_lines:
                continue
            new_po_vals.append({
                'partner_id': first_order.partner_id.id,
                'origin': ', '.join(origin_names),
                'order_line': order_lines,
                'x_sub_service_id': first_order.x_sub_service_id.id,
                'x_membership_plan_id': first_order.x_membership_plan_id.id,
            })

        return new_po_vals, original_pos

    def _x_get_consolidation_notification(self, notification_type, message):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': notification_type,
                'message': message,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def _x_ike_check_automatic_rfq(self):
        """ Si los costos de convenio coinciden con los costos de evento, es candidato a ser enviado """
        self.ensure_one()
        auto_send_rfq = self._x_ike_check_costs()
        if not auto_send_rfq:
            return

        ir_model_data = self.env['ir.model.data']
        template_id = ir_model_data._xmlid_lookup('purchase.email_template_edi_purchase')[1]

        ctx = {
            'default_model': 'purchase.order',
            'default_res_ids': self.ids,
            'default_template_id': template_id,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'email_notification_allow_footer': True,
            'force_email': True,
            'mark_rfq_as_sent': True,  # <- Esto activa el message_post de purchase.order
        }

        composer = self.env['mail.compose.message'].with_context(**ctx).create({
            'model': 'purchase.order',
            'res_ids': self.ids,
            'template_id': template_id,
            'composition_mode': 'comment',
        })

        composer.with_context(**ctx)._action_send_mail()
        # ToDo: Se dejará algún mensaje en el chatter?

    def _x_ike_check_costs(self):
        """ Validar linea por linea que coincidan los costos de convenio, si todos coincide, regresar True """
        self.ensure_one()
        return all(
            line.x_supplier_product_id.base_unit_price == line.price_unit
            for line in self.order_line
        )

    def x_action_start_consolidation(self):
        """Verificar si el proveedor tiene la configuración para consolidar las órdenes por batch.
        Marcar como 'to_consolidate', si no tiene, consolidar la orden actual."""
        self.ensure_one()
        self.write({'state': 'to_consolidate'})
        if not self.partner_id.x_has_consolidation:
            self.x_action_consolidate()

    # - - - - - - - - - - - - - #
    #           SAP             #
    # - - - - - - - - - - - - - #
    def x_syncronize_po_with_sap(self):
        """Enviar la orden a SAP."""
        # * Se realiza el proceso de autenticación SAP de forma lineal en el método principal,
        # * debido a que al intercambiar el token desde una función aparte se pierde el valor.
        access_token = False
        access_token_url = self.env['ir.config_parameter'].sudo().get_param('ike_event_purchase.url.getToken')
        username = self.env['ir.config_parameter'].sudo().get_param('ike_event_purchase.sap.username')
        password = self.env['ir.config_parameter'].sudo().get_param('ike_event_purchase.sap.password')
        headers = {'Content-Type': 'application/json'}
        login_body = {
            'petition': 'getToken',
            'user': username,
            'password': password,
        }
        try:
            response = requests.post(access_token_url, headers=headers, json=login_body)
            if response.status_code == 200:
                _logger.info("PO-SAP: successfully obtained access token")
                response_data = response.json()

                access_token = response_data.get('access_token', False)  # Obtener el token
            else:
                _logger.warning(f'PO-SAP: Error al obtener el token de acceso a SAP: {response}')
                for p in self:
                    try:
                        p.write({
                            'x_sap_connection_error_message': f'Error al obtener el token de acceso a SAP: {response}',
                            'x_sap_reference_received': False,
                        })
                    except Exception as e:
                        _logger.warning(f'PO-SAP: Error al actualizar el token de acceso a SAP: {str(e)}')
        except Exception as e:
            _logger.warning(f'PO-SAP: Error al obtener el token de acceso a SAP: {str(e)}')
            for p in self:
                try:
                    p.write({
                        'x_sap_connection_error_message': f'Error al obtener el token de acceso a SAP: {str(e)}',
                        'x_sap_reference_received': False,
                    })
                except Exception as e:
                    _logger.warning(f'PO-SAP: Error al actualizar el token de acceso a SAP: {str(e)}')

        if access_token:
            purchases_response = self.x_create_sap_order(access_token)
            for purchase_response in purchases_response:
                if purchase_response['response']:
                    order_data = purchase_response['response']
                    if order_data['code'] == '200' and 'detail' in order_data:
                        po_sap_id = order_data['detail']['purchaseOrder']
                        purchase = self.browse(purchase_response['order_id'])

                        if not po_sap_id:
                            try:
                                purchase.write({
                                    'x_ref_sap': po_sap_id,
                                    'x_sap_connection_error_message': order_data['detail']['message'],
                                    'x_sap_reference_received': False,
                                })
                            except Exception as e:
                                _logger.warning(f'PO-SAP: Error al actualizar el token de acceso a SAP: {str(e)}')
                            continue

                        try:
                            purchase.write({
                                'x_ref_sap': po_sap_id,
                                'x_sap_connection_error_message': "",
                                'x_sap_reference_received': True,
                            })
                        except Exception as e:
                            _logger.warning(f'PO-SAP: Error al actualizar el token de acceso a SAP: {str(e)}')
                        purchase.message_post(
                            body=_('SAP Reference: %s') % po_sap_id,
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                        )
                    else:
                        purchase = self.browse(purchase_response['order_id'])
                        try:
                            purchase.write({
                                'x_sap_connection_error_message': f'Error creando la orden en SAP: {order_data}',
                                'x_sap_reference_received': False,
                            })
                        except Exception as e:
                            _logger.warning(f'PO-SAP: Error al actualizar el token de acceso a SAP: {str(e)}')
                        purchase.message_post(
                            body=_('Error creating SAP order: %s') % order_data,
                            message_type='notification',
                            subtype_xmlid='mail.mt_note',
                        )
                else:
                    purchase = self.browse(purchase_response['order_id'])
                    try:
                        purchase.write({
                            'x_sap_connection_error_message': f'Error creando la orden en SAP: {purchase_response}',
                            'x_sap_reference_received': False,
                        })
                    except Exception as e:
                        _logger.warning(f'PO-SAP: Error al actualizar el token de acceso a SAP: {str(e)}')
                    purchase.message_post(
                        body=_('Error creating SAP order'),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )

            _logger.info(f"order_data: {purchases_response}")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'SAP',
                'message': 'Token obtenido correctamente.',
                'type': 'success',
                'sticky': False,
            }
        }

    def x_create_sap_order(self, access_token):
        # def parse_code_name(text: str) -> dict:
        #     match = re.match(r'^\[([^\]]+)\]\s*(.+)$', text.strip())
        #     if not match:
        #         raise ValueError(f"Formato inválido: '{text}'")
        #     return {
        #         'code': match.group(1),
        #         'name': match.group(2)
        #     }

        create_po_url = self.env['ir.config_parameter'].sudo().get_param('ike_event_purchase.url.createPurchaseOrder')
        headers = {
            'Authorization': access_token,
            'Content-Type': 'application/json'
        }

        purchase_reponses = []
        for purchase in self:
            account_id = purchase.x_membership_plan_id.account_id
            body = {
                "identifier": {
                    "tenants": "adff7f6a-e97d-11eb-9a03-0242ac130003",  # MX Tenant
                    "app": "IKE360"  # Identificador de la aplicación
                },
                "sap": {
                    "companyCode": account_id.x_invoice_company_id[0].name if account_id.x_invoice_company_id else "ARSA",
                    "supplier": str(purchase.partner_id.x_ref_sap).zfill(10),
                    "documentCurrency": str(purchase.currency_id.name),
                    "copago": "",  # * Se envía vacío
                    "incotermsLocation1": str(account_id.parent_id.x_ref_sap).zfill(10),
                    "incotermsLocation2": "",  # * Se envía vacío
                    "toPurchaseOrderItem": {
                        "results": [
                            {
                                "supplierMaterialNumber": line.x_concept_line_id.sap_id_income,  # Valor SAP ingeso de Plan de cobertura
                                "orderQuantity": str(line.product_qty),
                                "netPriceAmount": str(line.price_unit),
                                "material": line.x_concept_line_id.sap_id_outgoing,  # Valor SAP egreso de Plan de cobertura
                                "purchaseOrderQuantityUnit": "SER",
                                "expediente": str(line.x_parent_event_id.id)
                            } for line in purchase.order_line
                        ]
                    }
                }
            }
            _logger.info(f"Sending order to SAP: {body}")
            empty_response = {'order_id': purchase.id, 'response': False}
            try:
                order_response = requests.post(create_po_url, headers=headers, json=body)
                if order_response.status_code == 200:
                    order_data = order_response.json()
                    purchase_reponses.append({'order_id': purchase.id, 'response': order_data})
                    _logger.info(f"PO-SAP: successfully created order {order_data}")
                else:
                    _logger.warning(f'PO-SAP: Error al crear la orden en SAP: {order_response.text}')
                    purchase_reponses.append(empty_response)
            except Exception as e:
                _logger.warning(f'PO-SAP: Error al crear la orden en SAP: {str(e)}')
                purchase_reponses.append(empty_response)
        return purchase_reponses

    @api.model
    def _cron_done_tickets_from_draft_po(self):
        """
        Search for draft Purchase Orders based and process their associated helpdesk tickets.
        """
        # Get the current date relative to the user/server context
        today = fields.Date.context_today(self)

        domain = [
            ('state', '=', 'draft'),
            ('x_event_id', '!=', False),
            ('date_planned', '<=', today),
            ('sh_purchase_ticket_ids', '!=', False),
            ('x_dispute_state', '=', 'none'),
        ]

        orders = self.search(domain)
        _logger.info("Found %s Purchase Orders to process for ticket completion", len(orders))
        for order in orders:
            try:
                order.x_portal_action_accept_prices()
            except Exception as e:
                _logger.error("Failed to process tickets for PO %s: %s", order.name, str(e))

        return True
