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

    def action_save_info(self):
        self.ensure_one()
        service_id = self.env[self.service_res_model].browse(self.service_res_id)
        if self.service_res_model == 'ike.service.input.vial':
            service_id.write({
                'vehicle_brand': self.brand,
                'vehicle_model': self.model,
                'vehicle_plate': self.plate,
                'vehicle_color': self.color,
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
