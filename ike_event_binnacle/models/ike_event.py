# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import format_datetime

import logging
import ast
_logger = logging.getLogger(__name__)


class IkeEvent(models.Model):
    _inherit = 'ike.event'

    binnacle_html = fields.Html(copy=False)
    cancel_reason_text = fields.Text()

    duplicate_reason_id = fields.One2many('ike.event.duplicate.wizard', 'event_id')

    # === CRUD === #
    @api.model_create_multi
    def create(self, vals_list):
        result = super().create(vals_list)
        for rec in result:
            rec._create_message_binnacle([
                "ike_event_binnacle.ike_binnacle_stage_1_1",
                "ike_event_binnacle.ike_binnacle_stage_1_2",
                "ike_event_binnacle.ike_binnacle_stage_1_3",
                "ike_event_binnacle.ike_binnacle_stage_1_4"
            ])
        return result

    def _create_message_binnacle(self, binnacle_xmlids):
        """
        Create binnacle messages in chatter based on ike.event.binnacle records
        The text_html field is rendered using QWeb engine via message_post
        Args:
            binnacle_xmlids (list): List of XML IDs referencing ike.event.binnacle records
        Returns:
            recordset: Created mail.message records
        """
        self.ensure_one()
        if not binnacle_xmlids:
            return self.env['mail.message']
        created_messages = self.env['mail.message']
        for xmlid in binnacle_xmlids:
            try:
                # Get the binnacle record using the XML ID
                binnacle = self.env.ref(xmlid, raise_if_not_found=False)
                if not binnacle.binnacle_template_id:  # type: ignore
                    _logger.warning(f'Binnacle record template with XML ID "{xmlid}" not found')
                    continue
                template_results = binnacle.with_context(  # type: ignore
                    lang=self.env.user.lang
                ).binnacle_template_id._generate_template(  # type: ignore
                    self.ids,
                    (
                        'attachment_ids',
                        'auto_delete',
                        'body_html',
                        'email_cc',
                        'email_from',
                        'email_to',
                        'mail_server_id',
                        'model',
                        'partner_to',
                        'reply_to',
                        'report_template_ids',
                        'res_id',
                        'scheduled_date',
                        'subject',
                    ),
                )
                message = template_results.get(self.id, False)
                if message:
                    body_html = message.get('body_html')
                    subject = message.get('subject')
                    # Post message using message_post (supports QWeb)
                    message = self.with_context(lang=self.env.user.lang).sudo().message_post(
                        body=body_html,
                        subject=subject,
                        message_type='notification',
                        subtype_xmlid='mail.mt_discuss',
                        author_id=self.env.user.partner_id.id,
                    )
                    # Add the event_binnacle_id to the created message
                    if message:
                        message.sudo().write({
                            'event_binnacle_id': binnacle.id,  # type: ignore
                            'parent_id': False,
                        })
                        created_messages |= message
                    _logger.info(f'Created binnacle message for event {self.name} from {xmlid}')
            except Exception as e:
                _logger.error(f'Error creating binnacle message from {xmlid}: {e}')
                continue
        return created_messages

    def _get_messages_binnacle_from_event(self):
        # ToDo delete after testing the widget
        message_ids = self.env['mail.message'].sudo().search([
            ('event_binnacle_id', '!=', False),
            ('model', '=', "ike.event"),
            ('res_id', '=', self.id)
        ], order='id desc')
        return message_ids

    def _get_message_process(self, message_ids):
        # ToDo delete after testing the widget
        # sorted_messages = message_ids.sorted(key=lambda m: m.id)
        rows = ''
        for message in message_ids:
            # Format date in user's timezone
            if message.create_date:
                # Option 1: Using Odoo's format_datetime (recommended)
                date_time = format_datetime(
                    self.env,
                    message.create_date,
                    dt_format='dd/MM/yyyy | HH:mm:ss'
                )
            else:
                date_time = ''

            # Get category
            category = message.event_binnacle_id.binnacle_category_id.name if message.event_binnacle_id else ''
            # Get comments
            comments = message.body or ''
            # Get author
            input_message = message.author_id.name if message.author_id else ''
            # Determine background class based on parent_id
            has_parent = (
                message.event_binnacle_id
                and message.event_binnacle_id.binnacle_category_id
                and message.event_binnacle_id.binnacle_category_id.parent_id
            )

            # Es comentario (wizard)
            is_comment = (
                message.message_type == 'comment'
            )

            # Determinar clase de fondo
            bg_class = ''
            if not has_parent and not is_comment:
                bg_class = 'bg-success bg-opacity-25'

            if not message.event_binnacle_id.binnacle_category_id.parent_id and not is_comment:
                rows += f'''
                    <tr class="{bg_class}">
                        <td>{date_time}</td>
                        <td class="fw-semibold text-dark">{category}</td>
                        <td></td>
                        <td>{input_message}</td>
                        <td>{comments}</td>
                    </tr>
                '''
            else:
                # Create row
                rows += f'''
                    <tr class="{bg_class}">
                        <td>{date_time}</td>
                        <td>{category}</td>
                        <td></td>
                        <td>{input_message}</td>
                        <td>{comments}</td>
                    </tr>
                '''

        # Build complete message
        message = f'''
            <p data-oe-version="1.2">&nbsp;<br></p>
            <table class="table table-sm table-bordered mb-0">
                <thead class="text-white fw-semibold" style="background-color: #488ECC;">
                    <tr>
                        <th>Fecha y hora</th>
                        <th>Categoría</th>
                        <th>Proveedor</th>
                        <th>Entrada</th>
                        <th>Comentarios</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
        '''
        return message

    def action_open_view_binnacle_html(self):
        # ToDo delete after testing the widget
        message_ids = self._get_messages_binnacle_from_event()

        self.binnacle_html = self._get_message_process(message_ids)
        self.ensure_one()

        return {
            'name': _('Binnacle'),
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event',
            'view_mode': 'form',
            'views': [(self.env.ref('ike_event_binnacle.view_binnacle_event_form').id, 'form')],
            'target': 'new',
            'res_id': self.id,
            'domain': [('id', '=', self.id)],
            'context': dict(self.env.context),
        }

    def action_open_view_comment_wizard(self):
        self.ensure_one()
        return {
            'name': _('Add Comment'),
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.comment.wizard',
            'target': 'new',
            'context': {
                'default_event_id': self.id,
            }
        }

    def action_set_user_data(self):
        result = super(IkeEvent, self).action_set_user_data()
        for rec in self:
            # rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_2_1"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_2_4"])
        return result

    def action_set_user_service_data(self):
        result = super(IkeEvent, self).action_set_user_service_data()
        for rec in self:
            # rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_2"])
            # rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_3"])
            # rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_4"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_5"])
        return result

    def action_set_location_data(self):
        result = super(IkeEvent, self).action_set_location_data()
        for rec in self:
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_6"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_7"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_8"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_9"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_10"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_11"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_12"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_13"])
        return result

    def action_set_survey_data(self):
        result = super(IkeEvent, self).action_set_survey_data()
        for rec in self:
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_14"])
        return result

    def action_set_destination_data(self):
        result = super(IkeEvent, self).action_set_destination_data()
        for rec in self:
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_15"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_16"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_4_1"])

        return result

    def action_set_user_sub_service_data(self):
        result = super(IkeEvent, self).action_set_user_sub_service_data()
        for rec in self:
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_4_2"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_4_3"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_4_4"])
            rec._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_5_1"])
        return result


class IkeEventSupplier(models.Model):
    _inherit = 'ike.event.supplier'

    def action_assign(self):
        result = super(IkeEventSupplier, self).action_assign()
        for rec in self:
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_5_2"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_5_3"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_5_4"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_5_5"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_6_1"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_1"])
            rec.event_id.with_context(
                current_supplier_id=rec.id)._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_2"])
        return result

    def action_on_route(self):
        result = super(IkeEventSupplier, self).action_on_route()
        for rec in self:
            rec.event_id.with_context(
                current_supplier_id=rec.id)._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_3"])
        return result

    def action_arrive(self):
        result = super(IkeEventSupplier, self).action_arrive()
        for rec in self:
            rec.event_id.with_context(
                current_supplier_id=rec.id)._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_4"])
        return result

    def action_on_route_to_the_destination(self):
        result = super(IkeEventSupplier, self).action_on_route_to_the_destination()
        for rec in self:
            rec.event_id.with_context(
                current_supplier_id=rec.id)._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_13"])

        return result

    def action_arrive_to_the_destination(self):
        result = super(IkeEventSupplier, self).action_arrive_to_the_destination()
        for rec in self:
            rec.event_id.with_context(
                current_supplier_id=rec.id)._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_14"])

        return result

    def action_finalize(self):
        result = super(IkeEventSupplier, self).action_finalize()
        for rec in self:
            rec.event_id.with_context(
                current_supplier_id=rec.id)._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_22"])
        return result

    class IkeEventSupplierLink(models.Model):
        _inherit = 'ike.event.supplier.link'

        def action_accept_authorization(self):
            result = super().action_accept_authorization()
            for rec in self:
                rec.event_id.with_context(
                    supplier_link_id=rec.id
                )._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_13_1"])
            return result

        def action_request_authorization(self):
            result = super().action_request_authorization()
            for rec in self:
                rec.event_id.with_context(
                    supplier_link_id=rec.id
                )._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_5"])
                rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_9"])
                rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_10"])
                # rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_12"])

            return result


class IkeEventAffiliationUser(models.TransientModel):
    _inherit = 'ike.add.affiliation.nu'

    def action_save(self):
        result = super().action_save()
        for rec in self:
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_3_1"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_23"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_24"])

        return result


class IkeEventMembershipAuthorization(models.Model):
    _inherit = 'ike.event.membership.authorization'

    def action_authorized(self):
        result = super().action_authorized()
        for rec in self:
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_2_1"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_2_2"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_2_3"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_25"])
            # rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_26"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_27"])
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_29"])
        return result

    def action_rejected(self):
        result = super().action_rejected()
        for rec in self: 
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_31"])
        return result

    def send_mail_commercial_authorizator(self):
        result = super().send_mail_commercial_authorizator()
        for rec in self:
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_28"])
        return result

    def action_authorized_membership(self):
        result = super().action_authorized_membership()
        for rec in self:
            rec.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_7_30"])
        return result


class IkeEventConfirmWizard(models.TransientModel):
    _inherit = "ike.event.confirm.wizard"

    def action_confirm(self):
        res = super().action_confirm()

        rec_ids = ast.literal_eval(self.res_ids)
        records = self.env[self.res_model].browse(rec_ids)

        if self.res_model == 'ike.event':
            for event in records:
                event.cancel_reason_text = self.reason  # type: ignore

                event._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_8_1"])  # type: ignore

        elif self.res_model == 'ike.event.supplier':
            for supplier in records:
                supplier.event_id.cancel_reason_text = self.reason  # type: ignore
                supplier.event_id._create_message_binnacle(["ike_event_binnacle.ike_binnacle_stage_8_2"])  # type: ignore
        return res

    class IkeEventDuplicateWizard(models.TransientModel):
        _inherit = "ike.event.duplicate.wizard"

        def action_duplicate_event(self):
            result = super().action_duplicate_event()

            for rec in self:
                for reason in rec.event_id.duplicate_reason_id:
                    rec.event_id.with_context(
                        reason_name=reason.duplicate_reason_id.name  # type: ignore
                    )._create_message_binnacle(
                        ["ike_event_binnacle.ike_binnacle_stage_9_1"]
                    )

            return result
