from odoo import models, fields
import logging
_logger = logging.getLogger(__name__)


class IkeEventServiceAssistView(models.TransientModel):
    _name = 'ike.event.service.assistview'
    _description = 'Service Assist View'

    event_id = fields.Many2one('ike.event', string='Event', required=True)
    # service_id = fields.Many2one('ike.service', string='Service', required=True)
    service_res_model = fields.Char(string='Service Resource Model')
    service_res_id = fields.Integer(string='Service Resource ID')
    service_survey_input_id = fields.Many2one('ike.service.survey.input', string='Service Survey Input')
    received_assistview = fields.Boolean(string='Received Assistview', default=False)
    created_lambda_session = fields.Boolean(string='Created Lambda Session', default=False)
    sended_whatsapp_message = fields.Boolean(string='Sended Whatsapp Message', default=False)
    sended_whatsapp_confirmation = fields.Boolean(string='Sended Whatsapp Confirmation', default=False)

    # ike.service.input.vial fields
    vin = fields.Char(string='VIN')
    brand = fields.Char(string='Brand')
    model = fields.Char(string='Model')
    plate = fields.Char(string='Plate')
    color = fields.Char(string='Color')
    latitude = fields.Char(string='Latitude')
    longitude = fields.Char(string='Longitude')
    address = fields.Char(string='Address')
    answers = fields.Json(string='Answers')

    plate_image = fields.Image(string='Plate Image')

    vehicle_images = fields.One2many('ike.event.service.assistview.image', 'assistview_id', string='Vehicle Images')

    # Notificar al usuario que se recibió la información
    def write(self, vals):
        if 'plate_image' in vals and 'latitude' in vals and 'longitude' in vals:
            for rec in self:
                rec.send_whatsapp_confirmation()
        return super().write(vals)

    def send_whatsapp_confirmation(self):
        self.ensure_one()
        encryption_util = self.env['custom.encryption.utility']
        phone_number = encryption_util.decrypt_aes256(self.event_id.user_id.phone or '')
        wp_access_token = self.env['ike.event.supplier'].x_get_whatsapp_token()
        return self.env['ike.event.supplier'].x_send_whatsapp_template(
            access_token=wp_access_token,
            event_id=str(self.event_id.id),
            template=68,  # confirmacion
            phone_number=phone_number,
        )

    def action_save_info(self):
        self.ensure_one()
        service_id = self.env[self.service_res_model].browse(self.service_res_id)
        if self.service_res_model == 'ike.service.input.vial':
            service_id.write({
                'vehicle_brand': self.brand,
                'vehicle_model': self.model,
                'vehicle_plate': self.plate,
                'vehicle_color': self.color,
                'vehicle_plate_image': self.plate_image,
            })
            event_data = {}
            change_latitude_or_longitude = False
            if self.latitude:
                event_data['location_latitude'] = self.latitude
                change_latitude_or_longitude = True
            if self.longitude:
                event_data['location_longitude'] = self.longitude
                change_latitude_or_longitude = True
            if event_data:
                self.event_id.write(event_data)
            if change_latitude_or_longitude:
                self.event_id._onchange_location()

        if len(self.vehicle_images) > 0:
            nu_evidence_id = self.event_id.service_evidence_ids.filtered(lambda x: x.evidence_type == 'nu_evidence')
            if not nu_evidence_id:
                nu_evidence_id = self.env['ike.event.evidence'].create({
                    'event_id': self.event_id.id,
                    'evidence_type': 'nu_evidence',
                })
            evidences = []
            for image in self.vehicle_images:
                evidences.append((0, 0, {
                    'file_name': image.image_name,
                    'file_image': image.image,
                    'side': '',
                }))
            nu_evidence_id.write({
                'detail_ids': evidences,
            })


class IkeEventServiceAssistViewImage(models.TransientModel):
    _name = 'ike.event.service.assistview.image'
    _description = 'Service Assist View Image'

    assistview_id = fields.Many2one('ike.event.service.assistview', string='Assist View', required=True)
    image = fields.Image(string='Image')
    image_name = fields.Char(string='Image Name')
