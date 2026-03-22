# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IkeServiceInputVialTruck(models.Model):
    _name = 'ike.service.input.vial.truck'
    _inherit = ['ike.service.input.vial.base']
    _description = 'Service Input Vial Town Truck'

    # IA Suggestion fields in base model
    service_vehicle_type_ids = fields.Many2many(
        'custom.vehicle.type',
        'ike_service_vial_truck_vehicle_type_rel', 'sub_service_id', 'vehicle_type_id',
        string='Service Vehicle Types', copy=False)
    service_accessory_ids = fields.Many2many(
        'product.product',
        'ike_service_vial_truck_accessories_rel',
        'sub_service_id', 'accessories_id',
        string='Accessories', copy=False)

    # Destination
    destination_label = fields.Char(related='event_id.destination_label', readonly=False)
    destination_latitude = fields.Char(related='event_id.destination_latitude', readonly=False)
    destination_longitude = fields.Char(related='event_id.destination_longitude', readonly=False)
    destination_distance = fields.Float(related='event_id.destination_distance', readonly=False)
    destination_duration = fields.Float(related='event_id.destination_duration', readonly=False)
    destination_route = fields.Json(related='event_id.destination_route', readonly=False)
    destination_zip_code = fields.Char(related='event_id.destination_zip_code', readonly=False)

    # Destination Data
    street = fields.Char()
    street2 = fields.Char(string='Between streets')
    city = fields.Char()
    colony = fields.Char()
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    state_id = fields.Many2one(
        "res.country.state", string='State', ondelete='restrict',
        domain="[('country_id', '=', country_id)]")
    # municipality = fields.Char()
    municipality_id = fields.Many2one(
        'custom.state.municipality', string='Municipality', ondelete='restrict',
        domain="[('state_id', '=', state_id)]")
    street_ref = fields.Char(string='References')
    street_number = fields.Char()
    destination_highway = fields.Boolean(string='Is destination a Highway?')
    service_product_ids = fields.One2many(
        related='event_id.service_product_ids',
        string='Service concepts',
        readonly=False,
        copy=False,
    )

    # === METHODS === #
    def set_event_summary_user_subservice_data(self):
        pass
