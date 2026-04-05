# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class IkeEventVehicleWizard(models.TransientModel):
    _name = 'ike.event.vehicle.wizard'
    _description = 'Event Vehicle Info Wizard'

    event_id = fields.Many2one('ike.event', readonly=True)
    latitude = fields.Char(related='event_id.location_latitude')
    longitude = fields.Char(related='event_id.location_longitude')

    vehicle_ids = fields.One2many('ike.event.vehicle.detail.wizard', 'wizard_id', readonly=True)


class IkeEventVehicleDetailWizard(models.TransientModel):
    _name = 'ike.event.vehicle.detail.wizard'

    wizard_id = fields.Many2one('ike.event.vehicle.wizard')
    vehicle_id = fields.Many2one('fleet.vehicle', 'Vehicle')
    vehicle_ref = fields.Char()
    vehicle_type_id = fields.Many2one(related='vehicle_id.x_vehicle_type', string='Vehicle Type')
    supplier_center_id = fields.Many2one(related='vehicle_id.x_center_id', string='Supplier Center')

    latitude = fields.Char()
    longitude = fields.Char()
    distance_km = fields.Float('Distance (km)')
    duration_m = fields.Float('Duration (min)')
    external_location = fields.Boolean()
    external_latitude = fields.Char()
    external_longitude = fields.Char()
    external_distance_km = fields.Float('External Distance (km)')
    external_duration_m = fields.Float('External Duration (min)')
