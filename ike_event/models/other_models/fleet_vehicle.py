from odoo import models, fields


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    def move_location_vehicle(self):

        message = {
            'vehicles': [
                {
                    'id': rec.id,
                    'x_latitude': float(rec.x_latitude),
                    'x_longitude': float(rec.x_longitude),
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
