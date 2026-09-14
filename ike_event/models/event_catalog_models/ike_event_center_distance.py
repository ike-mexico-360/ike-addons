# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _


class IkeEventCenterDistance(models.Model):
    _name = 'ike.event.center.distance'
    _description = 'Event Supplier Center Distance'

    event_id = fields.Many2one('ike.event', required=True, ondelete='cascade', index=True)
    supplier_center_id = fields.Many2one('res.partner', required=True, ondelete='cascade', index=True)
    supplier_id = fields.Many2one(related='supplier_center_id.parent_id')

    latitude = fields.Float()
    longitude = fields.Float()

    center_origin_distance_km = fields.Float(default=0.0)
    center_origin_duration_m = fields.Float(default=0.0)
    center_origin_route = fields.Json()
    origin_center_distance_km = fields.Float(default=0.0)
    origin_center_duration_m = fields.Float(default=0.0)
    origin_center_route = fields.Json()
    destination_center_distance_km = fields.Float(default=0.0)
    destination_center_duration_m = fields.Float(default=0.0)
    destination_center_route = fields.Json()

    @api.depends('event_id', 'supplier_center_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.event_id.name} - {rec.supplier_center_id.name}'
