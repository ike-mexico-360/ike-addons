# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.osv import expression


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    _aux_truck_order = 'x_vehicle_service_state, license_plate'

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if not self.env.context.get('aux_truck_order_by_state'):
            return super().name_search(name, args, operator, limit)
        domain = expression.AND([[('display_name', operator, name)], args or []])
        records = self.search_fetch(domain, ['display_name'], limit=limit, order=self._aux_truck_order)
        return [(record.id, record.display_name) for record in records.sudo()]

    def move_location_vehicle(self):
        message = {
            'vehicles': [
                {
                    'id': rec.id,
                    'x_latitude': rec.x_latitude,
                    'x_longitude': rec.x_longitude,
                    'x_vehicle_service_state': rec.x_vehicle_service_state,
                }
                for rec in self
            ]
        }

        if not message['vehicles']:
            return

        self.env['bus.bus']._sendone(
            target='custom_fleet_dashboard',
            notification_type='update_location_vehicle',
            message=message,
        )
