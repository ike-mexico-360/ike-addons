from odoo import models, api
import logging
_logger = logging.getLogger(__name__)


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    @api.model
    def cron_push_location_updates(self, vehicle_ids=None, limit=500):
        """Pensado para jecución en cron, pero lo llamaremos directo.

        Es un bypass a move_location_vehicle ya que debe ejecutarse en en enviroment de Odoo
        pero el LocationBatcher se ejecuta en un hilo independiente
        """
        domain = []
        if vehicle_ids:
            domain = [
                ('id', 'in', vehicle_ids),
                ('x_vehicle_service_state', 'in', ('available', 'in_service')),
            ]

        vehicles = self.env['fleet.vehicle'].search(domain, limit=limit)
        if not vehicles:
            return

        _logger.info("cron_push_location_updates: vehicles=%s", vehicles.ids)
        vehicles.move_location_vehicle()
