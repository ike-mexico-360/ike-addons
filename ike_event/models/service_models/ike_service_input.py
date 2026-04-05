# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IkeServiceInput(models.AbstractModel):
    _name = 'ike.service.input'
    _description = 'Service Input'

    name = fields.Char(copy=False)
    event_id = fields.Many2one('ike.event', required=True, ondelete='cascade', index=True)
    stage_ref = fields.Char(related='event_id.stage_ref')
    step_number = fields.Integer(related='event_id.step_number')
    supplier_number = fields.Integer(related='event_id.supplier_number')
    sections = fields.Json(related='event_id.sections')
    service_id = fields.Many2one(related='event_id.service_id')
    sub_service_id = fields.Many2one(related='event_id.sub_service_id')
    active = fields.Boolean(default=True)

    service_product_ids = fields.One2many(
        related='event_id.service_product_ids',
        string='Service concepts',
        readonly=False,
        copy=False,
    )

    ia_suggestion_loading = fields.Boolean()

    def set_event_summary_event_data(self):
        pass

    @api.model
    def get_google_api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')

    def write(self, vals):
        # To Fix related and readonly=False. for some kind weird reason is and ike.event field o2m field set not an unlink
        if 'service_product_ids' in vals:
            to_delete = [x[1] for x in vals['service_product_ids'] if x[0] == 2]  # 2 == UNLINK
            others = [x for x in vals['service_product_ids'] if x[0] != 2]
            vals['service_product_ids'] = others
            event_product_ids = self.env['ike.event.product'].browse(to_delete)
            event_product_ids.unlink()
        return super().write(vals)


class IkeServiceInputModel(models.AbstractModel):
    _name = 'ike.service.input.model'
    _inherit = ['ike.service.input']
    _description = 'Service Input Model'

    service_date = fields.Datetime(default=fields.Datetime.now, copy=False)

    # Location
    location_label = fields.Char(related='event_id.location_label', readonly=False)
    location_latitude = fields.Char(related='event_id.location_latitude', readonly=False)
    location_longitude = fields.Char(related='event_id.location_longitude', readonly=False)
    location_zip_code = fields.Char(related='event_id.location_zip_code', store=False, readonly=False)
    requires_federal_plates = fields.Boolean(related='event_id.requires_federal_plates', readonly=False)
    event_type_id = fields.Many2one(related='event_id.event_type_id', readonly=False)

    # Location Data
    street = fields.Char()
    street2 = fields.Char(string='Between streets')
    city = fields.Char()
    colony = fields.Char()
    # municipality = fields.Char()
    municipality_id = fields.Many2one(
        'custom.state.municipality', string='Municipality', ondelete='restrict',
        domain="[('state_id', '=', state_id)]")
    state_id = fields.Many2one(
        'res.country.state', string='State', ondelete='restrict',
        domain="[('country_id', '=', country_id)]")
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    street_ref = fields.Char(string='References')
    street_number = fields.Char()

    @api.onchange('event_type_id')
    def _onchange_event_type_id(self):
        if self.event_type_id:
            self.requires_federal_plates = self.event_type_id.requires_federal_plates

    def set_event_summary_user_service_data(self):
        pass

    def set_event_summary_location_data(self):
        pass

    def set_event_summary_survey_data(self):
        pass

    def set_event_summary_destination_data(self):
        pass

    def set_event_summary_user_sub_service_data(self):
        pass

    def set_event_summary_supplier_data(self):
        pass
