
import random
import base64
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class IkeEvent(models.Model):
    _inherit = 'ike.event'

    created_from_bp = fields.Boolean(
        string="Created from BP", copy=False,
        help="Technical (BP): Flag to indicate that the current event was created from a call from the BrightPattern service")
    temporary_phone = fields.Char(
        string="Temporary phone", copy=False,
        help="Technical (BP): This field will temporarily store the value received from BrightPattern when there is no record matching the phone number.")
    temporary_key_indentification = fields.Char(
        string="Temporary key identification", copy=False,
        help="Technical (BP): Field that temporarily stores the value received from Bright Pattern when there is no record matching the identification key.")
    temporary_membership_plan_id = fields.Many2one(
        'custom.membership.plan', string="Temporary account", copy=False,
        help="Technical (BP): Field that temporarily stores the coverage plan value corresponding to the BrightPattern call")

    def _get_default_random_user_code(self):
        """Generar código aleatorio de 6 dígitos no repetido"""
        self.env.cr.execute("""
            SELECT user_code
            FROM ike_event
            WHERE user_code IS NOT NULL
            ORDER BY event_date DESC
            LIMIT 200;
        """)
        user_codes = self.env.cr.dictfetchall()

        # Crear un set con los códigos existentes para búsqueda rápida
        existing_codes = {record['user_code'] for record in user_codes}

        # Generar un código no repetido
        max_attempts = 1000
        for __ in range(max_attempts):
            new_code = str(random.randint(100000, 999999))
            if new_code not in existing_codes:
                return new_code

        # Si no encuentra uno único después de max_attemps, retornar cualquiera
        return str(random.randint(100000, 999999))

    event_progress_state = fields.Selection([
        ('0', 'Not assigned'),
        ('1', 'Service started'),
        ('2', 'Arrived at first destination'),
        ('3', 'Validate code'),
        ('4', 'Sent second form'),
        ('5', 'Arrived at second destination'),
        ('6', 'Finalized')
        # ('0', 'Not assigned'),
        # ('1', 'Service started'),
        # ('2', 'Arrived at first destination'),
        # ('3', 'Submitted the first form'),
        # ('4', 'Arrived at second destination'),
        # ('5', 'Sent second form'),
        # ('6', 'Finalized')
    ], string="Event progress state", default='0', required=True,
        help="Indicates the current progress of the event in the app.")
    user_code = fields.Char(
        string="User code", size=6, default=lambda self: self._get_default_random_user_code(), required=True,
        help="User code to identify notifications from the app. This code must be random and 6 digits long.")

    pdf_report_of_finalization = fields.Binary(
        string='Finalization Report', attachment=True, copy=False, readonly=False)
    pdf_report_generated_date = fields.Datetime(
        string='Report Generation Date', readonly=True)

    @api.constrains('user_code')
    def _check_user_code_length(self):
        """Validar que user_code siempre tenga exactamente 6 dígitos"""
        for record in self:
            if record.user_code:
                if not record.user_code.isdigit():
                    raise ValidationError("The user code must be a number.")
                if len(record.user_code) != 6:
                    raise ValidationError("The user code must have 6 digits.")

    def button_regenerate_pdf_of_end_service(self):
        """Botón para regenerar el PDF de finalización de servicio"""
        self.ensure_one()
        self._ike_event_generate_pdf_of_end_service()

    def _ike_event_generate_pdf_of_end_service(self):
        """Generar PDF de finalización de servicio"""
        self.ensure_one()
        pdf_content = self.env['ir.actions.report'].sudo()._render_qweb_pdf(
            'ike_event_api.action_ike_event_end_service_report',
            [self.id]
        )[0]

        _logger.warning(f'PDF antes de guardar: {len(pdf_content)} bytes')

        self.sudo().pdf_report_of_finalization = base64.b64encode(pdf_content)
        self.sudo().pdf_report_generated_date = fields.Datetime.now()

        _logger.info(f'PDF generado para evento {self.id}')

    @api.constrains('stage_id')
    def _auto_generate_pdf_of_end_service(self):
        """Generar PDF de finalización de servicio"""
        end_stage_id = self.env.ref('ike_event.ike_event_stage_completed')
        for rec in self:
            if rec.stage_id.id == end_stage_id.id and not rec.pdf_report_of_finalization:
                _logger.warning('Generando PDF de finalización de servicio')

                try:
                    rec._ike_event_generate_pdf_of_end_service()
                except Exception as e:
                    _logger.error(f'Error al generar PDF: {str(e)}', exc_info=True)
                    raise ValidationError(_('Error: %s') % str(e))

    @api.constrains('stage_id')
    def _check_to_send_whatsapp_notification(self):
        """Send whatsapp notifications"""
        in_progress_stage_ref = self.env.ref('ike_event.ike_event_stage_in_progress').ref
        end_stage_ref = self.env.ref('ike_event.ike_event_stage_completed').ref
        for rec in self:
            try:
                # Evento en progreso
                if rec.stage_ref == in_progress_stage_ref and rec.step_number == 1:
                    rec._ike_event_send_whatsapp_notification('in_progress')
                # Evento concluido
                elif rec.stage_ref == end_stage_ref and rec.step_number == 1:
                    rec._ike_event_send_whatsapp_notification('completed')
            except Exception as e:
                _logger.error(f'Error al enviar notificación WhatsApp: {str(e)}', exc_info=True)

    def _ike_event_send_whatsapp_notification(self, stage_ref):
        """Send whatsapp notifications"""
        self.ensure_one()

        _logger.warning(f"Sending whatsapp notifications for event at change stage_id {stage_ref}")

        encryption_util = self.env['custom.encryption.utility']
        phone_number = encryption_util.decrypt_aes256(self.user_id.phone or '')

        # Si cambia a en progreso, se envía template 72, con el enlace de seguimiento
        if stage_ref == 'in_progress':
            on_route_supplier_stage = self.env.ref('ike_event.ike_service_stage_on_route')
            on_route_suppliers = self.selected_supplier_ids.filtered(lambda x: x.stage_id.id == on_route_supplier_stage.id)
            if on_route_suppliers:
                wp_access_token = self.env['ike.event.supplier'].x_get_whatsapp_token()
                self.env['ike.event.supplier'].x_send_whatsapp_template(
                    access_token=wp_access_token,
                    event_id=str(self.id),
                    template=72,  # LinkUsuario
                    phone_number=phone_number,
                    parameter=str(on_route_suppliers[0].travel_tracking_url),
                )

        # Si cambia a concluido, se envían 70 y 73
        elif stage_ref == 'completed':
            wp_access_token = self.env['ike.event.supplier'].x_get_whatsapp_token()
            self.env['ike.event.supplier'].x_send_whatsapp_template(
                access_token=wp_access_token,
                event_id=str(self.id),
                template=70,  # terminó
                phone_number=phone_number,
            )

            survey_url = self.satisfaction_survey_input_url
            self.env['ike.event.supplier'].x_send_whatsapp_template(
                access_token=wp_access_token,
                event_id=str(self.id),
                template=73,  # encuestaUser
                phone_number=phone_number,
                parameter=survey_url
            )

    def action_verify(self):
        """ Overrride action_verify to add 1 event to the event_count_detail_ids """
        res = super().action_verify()
        sub_service_id = self.sub_service_id
        matching_detail_ids = self.user_membership_id.event_count_detail_ids.filtered(lambda x: sub_service_id.id in x.sub_service_ids.ids)
        for detail in matching_detail_ids:
            detail.write({
                'events_of_period': detail.events_of_period + 1,
            })
        return res
