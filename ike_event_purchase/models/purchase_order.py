import re
import logging
import requests
# from urllib.parse import urlparse, parse_qs
from collections import defaultdict
from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError
# from markupsafe import Markup
from werkzeug.urls import url_encode

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(selection_add=[
        ('to_consolidate', 'To Consolidate'),
        ('consolidated', 'Consolidated'),
        ('purchase',),  # Ancla de posición
    ])
    x_event_id = fields.Many2one('ike.event', 'Event')
    x_sub_service_id = fields.Many2one('product.product', string='Subservice')
    x_membership_plan_id = fields.Many2one('custom.membership.plan', string='Membership Plan')
    x_dispute_state = fields.Selection([
        ('none', 'No Dispute'),
        ('open', 'Open'),
        ('submitted', 'Submitted'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ], string='Dispute State', default='none')
    x_dispute_approved = fields.Boolean(string='Dispute Approved', default=False)
    x_ref_sap = fields.Char(string='SAP Reference')

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        # Si es creado desde eventos
        if self._context.get('ike_event_purchase'):
            for purchase_id in res:
                purchase_id._x_ike_check_automatic_rfq()
        return res

    def _x_prepare_grouped_data(self, rfq):
        return (rfq.partner_id.id, rfq.x_membership_plan_id.id, rfq.x_sub_service_id.id)

    def x_action_consolidate(self):
        disputed_pos = self.filtered(lambda r: r.x_dispute_state in ('open', 'submitted'))
        if disputed_pos:
            raise UserError(_(
                'The following orders have an open or submitted dispute and cannot be consolidated:\n%s'
            ) % '\n'.join(disputed_pos.mapped('name')))

        try:
            rfq_to_consolidate = self.filtered(lambda r: r.state in ['to_consolidate'])

            rfqs_grouped = defaultdict(lambda: self.env['purchase.order'])
            for rfq in rfq_to_consolidate:
                key = self._x_prepare_grouped_data(rfq)
                rfqs_grouped[key] += rfq

            bunches_of_rfq_to_be_consolidate = list(rfqs_grouped.values())

            to_create_rfqs = []
            for rfqs in bunches_of_rfq_to_be_consolidate:
                group_concepts = {
                    'purchase_ids': rfqs,
                    'partner_id': rfqs.partner_id.id,
                    'extra_sub_total': {},  # Para la suma de subtotal de lineas que no tienen concepto detallado, por id de compra
                    'line_ids': {},
                }  # Agrupar por (po_name, product_description_po, sap_id_outgoing)

                for rfq in rfqs:
                    membership_plan_id = rfq.x_membership_plan_id
                    extra_sub_total = 0.0

                    all_products = rfqs.order_line.mapped('product_id')
                    concepts = self.env['custom.membership.plan.line.product'].search([
                        ('product_id', 'in', all_products.ids),
                        ('line_id.membership_plan_id', 'in', rfqs.mapped('x_membership_plan_id').ids),
                    ])
                    concept_map = {(c.product_id.id, c.line_id.membership_plan_id.id): c for c in concepts}
                    for rfq_line in rfq.order_line:
                        detailed_concept_id = concept_map.get((rfq_line.product_id.id, membership_plan_id.id), False)
                        if detailed_concept_id:
                            sap_key = (rfq_line.order_id.id, detailed_concept_id.line_id.product_description_po, detailed_concept_id.line_id.sap_id_outgoing)
                            if sap_key not in group_concepts['line_ids']:
                                group_concepts['line_ids'][sap_key] = []
                            group_concepts['line_ids'][sap_key].append({
                                'purchase_line_id': rfq_line.id,
                                'concept_line_id': detailed_concept_id.line_id.id,
                                'product_description_po': detailed_concept_id.line_id.product_description_po,
                                'sap_id_outgoing': detailed_concept_id.line_id.sap_id_outgoing,
                                'price_subtotal': rfq_line.price_subtotal,
                                'description': f"[{detailed_concept_id.line_id.sap_id_outgoing}] {detailed_concept_id.line_id.product_description_po} - {rfq_line.order_id.name}",  # ToDo: No se usará
                                'product_id': detailed_concept_id.line_id.sub_service_ids[:1].id or False,  # ToDo: Será el producto configurado como SAP
                            })
                        else:
                            extra_sub_total += rfq_line.price_subtotal
                    group_concepts['extra_sub_total'][rfq.id] = extra_sub_total

                if group_concepts:
                    to_create_rfqs.append(group_concepts)

            new_pos = []
            consolidate_pos = self.env['purchase.order']
            for group_concepts in to_create_rfqs:
                data = {
                    'partner_id': group_concepts['partner_id'],
                    'origin': ', '.join(group_concepts['purchase_ids'].mapped('name')),
                    'order_line': [],
                }
                new_line_ids = [values for values in group_concepts['line_ids'].values() if len(values) > 0]
                if not len(new_line_ids):
                    continue
                for key, values in group_concepts['line_ids'].items():
                    purchase_id = key[0]
                    data['order_line'].append(Command.create({
                        'name': values[0]['description'],  # ToDo: No se usará
                        'product_id': values[0]['product_id'],  # ToDo: Será el producto configurado como SAP
                        'product_qty': 1,
                        'price_unit': sum([line['price_subtotal'] for line in values] + [group_concepts['extra_sub_total'].get(purchase_id, 0.0)]),
                        'x_concept_line_id': values[0]['concept_line_id'],
                    }))
                new_pos.append(data)
                consolidate_pos += group_concepts['purchase_ids']

            new_po_ids = self.env['purchase.order'].create(new_pos)
            consolidate_pos.write({'state': 'consolidated'})
            new_po_ids.button_confirm()
            # new_po_ids.x_syncronize_po_with_sap()
        except Exception as e:
            _logger.error(e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'error',
                    'message': _('Error consolidating purchase orders'),
                    'next': {'type': 'ir.actions.act_window_close'},
                }
            }

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': _('Purchase orders consolidated'),
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
        equals_cost = []
        for purchase_line in self.order_line:
            equals_cost.append(bool(purchase_line.x_supplier_product_id.base_unit_price == purchase_line.price_unit))
        if all(equals_cost):
            return True
        return False

    def _x_action_start_dispute(self):
        """Proveedor no acepta propuesta de comprador, se inicia disputa"""
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
            ticket_ids = self.env['sh.helpdesk.ticket'].sudo().search([
                ('partner_id', '=', self.partner_id.id),
            ])
            ticket_id = ticket_ids.sudo().filtered(lambda x: self.id in x.sh_purchase_order_ids.ids)
            if not ticket_id.sudo():
                self.env['sh.helpdesk.ticket'].sudo().create({
                    'state': 'customer_replied',
                    'partner_id': self.partner_id.id,
                    'sh_purchase_order_ids': [(6, 0, [self.id])],
                })

    def x_get_dispute_url(self, confirm_type=None):
        """Create url for confirm or reject purchase dispute
        """
        if confirm_type in ['accept', 'decline']:
            param = url_encode({
                'dispute': confirm_type,
            })
            return f"/my/purchase/{self.id}/dispute?access_token={self._portal_ensure_token()}&{param}"
        return self.get_portal_url()

    def x_action_accept_prices(self):
        """El acepta los pecios tal cual están portal."""
        self.ensure_one()

        if self.x_dispute_state != 'none':
            raise UserError(_('There is a dispute on this order.'))

        for line in self.order_line:
            line.write({
                'x_price_unit_approved': line.unit_price,
                'x_product_qty_approved': line.product_qty,
            })

        self.x_action_start_consolidation()

    def x_action_start_consolidation(self):
        """Verificar si el proveedor tiene la configuración para consolidar las órdenes por batch.
        Marcar como 'to_consolidate', si no tiene, consolidar la orden actual."""
        self.ensure_one()
        self.write({'state': 'to_consolidate'})
        if not self.partner_id.x_has_consolidation:
            self.x_action_consolidate()

    def x_action_submit_dispute(self):
        """El proveedor confirma su propuesta de disputa desde el portal."""
        self.ensure_one()
        self._x_action_start_dispute()

        if self.x_dispute_state != 'open':
            raise UserError(_('There is no open dispute on this order.'))

        disputed_lines = self.order_line.filtered(
            lambda line: line.x_price_unit_dispute > 0 or line.x_product_qty_dispute > 0
        )
        if not disputed_lines:
            raise UserError(_('You must propose at least one new price or quantity before submitting.'))

        if self.x_dispute_state == 'submitted':
            raise UserError(_('This order already has a dispute submitted.'))

        self._x_start_sh_helpdesk_ticket()
        template = self.env.ref('ike_event_purchase.ike_event_purchase_proposal_dispute_ticket')
        ticket_ids_sudo = self.sudo().sh_purchase_ticket_ids
        for ticket in ticket_ids_sudo:
            template.sudo().with_context(dict(self._context, actual_order=self.id)).send_mail(ticket.id, force_send=True)
            self.message_post(
                body=_('The supplier has submitted their dispute proposal on ticket #%s.') % ticket.name,
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
        self.x_dispute_state = 'submitted'
        # Notificar al comprador interno (opcional)
        # self._x_notify_buyer_dispute_submitted()

    def x_action_approve_dispute(self):
        """Comprador acepta la propuesta del proveedor."""
        self.ensure_one()
        if self.x_dispute_state != 'submitted':
            raise UserError(_('There is no submitted dispute on this order.'))
        for line in self.order_line:
            vals = {}
            if line.x_price_unit_dispute:
                vals['x_price_unit_approved'] = line.x_price_unit_dispute
            if line.x_product_qty_dispute:
                vals['x_product_qty_approved'] = line.x_product_qty_dispute
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
        if self.partner_id.x_has_consolidation:
            self.x_action_consolidate()

    def x_action_send_new_values_rfq(self):
        """Send new values to RFQ."""
        self.ensure_one()
        if self.x_dispute_state != 'submitted':
            raise UserError(_('There is no submitted dispute on this order.'))
        # Validar que no hay campos aprobados en 0
        empty_vals = []
        for line in self.order_line:
            if line.x_price_unit_approved == 0 or line.x_product_qty_approved == 0:
                empty_vals.append(line.id)
        if empty_vals:
            raise UserError(_('There are zero approved values on lines.'))
        self.write({'x_dispute_state': 'resolved'})

    def x_action_reject_dispute(self):
        """Comprador rechaza la propuesta, se limpian los campos dispute."""
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
                'x_price_unit_approved': line.price_unit,
                'x_product_qty_dispute': line.product_qty,
            })

        self.write({'x_dispute_state': 'rejected'})

        self.message_post(
            body=body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            # body_is_html=True,
        )

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
        except Exception as e:
            _logger.warning(f'PO-SAP: Error al obtener el token de acceso a SAP: {str(e)}')

        if access_token:
            orders_data = self.x_create_sap_order(access_token)
            # ToDo: Crear campo en orden de compra para almacenar la respuesta de SAP
            # [{
            #     "odoo_id": 1,
            #     "code": "200",
            #     "detail": {"purchaseOrder": "5510", "message": "OK"}
            # }]
            _logger.info(f"order_data: {orders_data}")

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
        def parse_code_name(text: str) -> dict:
            match = re.match(r'^\[([^\]]+)\]\s*(.+)$', text.strip())
            if not match:
                raise ValueError(f"Formato inválido: '{text}'")
            return {
                'code': match.group(1),
                'name': match.group(2)
            }

        create_po_url = self.env['ir.config_parameter'].sudo().get_param('ike_event_purchase.url.createPurchaseOrder')
        headers = {
            'Authorization': access_token,
            'Content-Type': 'application/json'
        }

        for purchase in self:
            account_id = self.x_membership_plan_id.account_id
            body = {
                "identifier": {
                    "tenants": "adff7f6a-e97d-11eb-9a03-0242ac130003",  # MX Tenant
                    "app": "IKE360"  # Identificador de la aplicación
                },
                "sap": {
                    "companyCode": account_id.x_invoice_company_id[0] if account_id.x_invoice_company_id else "ARSA",
                    "supplier": str(self.partner_id.x_ref_sap),
                    "documentCurrency": str(self.currency_id.name),
                    "copago": "",  # * Se envía vacío
                    "incotermsLocation1": account_id.parent_id.x_ref_sap or "",
                    "incotermsLocation2": "",  # * Se envía vacío
                    "toPurchaseOrderItem": {
                        "results": [
                            {
                                "supplierMaterialNumber": line.x_concept_line_id.sap_id_income,  # Valor SAP ingeso de Plan de cobertura
                                "orderQuantity": str(line.product_qty),
                                "netPriceAmount": str(line.price_unit),
                                "material": line.x_concept_line_id.sap_id_outgoing,  # Valor SAP egreso de Plan de cobertura
                                "purchaseOrderQuantityUnit": "SER",
                                "expediente": str(self.x_event_id.id)
                            } for line in self.order_line
                        ]
                    }
                }
            }
            try:
                order_response = requests.post(create_po_url, headers=headers, json=body)
                if order_response.status_code == 200:
                    _logger.info("PO-SAP: successfully created order")
                    order_data = order_response.json()
                    return order_data
                else:
                    _logger.warning(f'PO-SAP: Error al crear la orden en SAP: {order_response.text}')
                    return False
            except Exception as e:
                _logger.warning(f'PO-SAP: Error al crear la orden en SAP: {str(e)}')
                return False
