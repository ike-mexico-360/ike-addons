from odoo import models, fields, api, _
from markupsafe import Markup


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    x_partner_id = fields.Many2one('res.partner', 'Partner', tracking=True)
    x_vehicle_type = fields.Many2one('custom.vehicle.type', 'Vehicle Type', tracking=True)
    x_product_category_id = fields.Many2one(
        'product.category', 'Service', related='x_vehicle_type.x_service_id', store=True, tracking=True)
    x_product_id = fields.Many2one(
        'product.product', 'Subservice', related='x_vehicle_type.x_subservice_id', store=True, tracking=True)
    x_federal_license_plates = fields.Boolean('Federal License Plates', tracking=True)
    x_category_ids = fields.Many2many(
        'fleet.vehicle.model.category', string='Categorías del vehículo', compute='_compute_vehicle_category_ids',
        store=True, tracking=True)
    x_maneuvers = fields.Boolean('Maneuvers', tracking=True)
    x_accessories = fields.Many2many(
        'product.product', string='Accessories', tracking=True,
        domain=lambda self: self.env['product.product'].get_accessories_domain())

    @api.depends('x_vehicle_type')  # , 'x_vehicle_type.x_vehicle_category_id')  # Solo si se requiere actualizar tras cada cambio
    def _compute_vehicle_category_ids(self):
        for vehicle in self:
            vehicle.x_category_ids = [x.id for x in vehicle.x_vehicle_type.x_vehicle_category_id]

    def action_disable(self, reason=None):
        if reason:
            body = Markup("""
                <ul class="mb-0 ps-4">
                    <li>
                        <b>{}: </b><span class="">{}</span>
                    </li>
                </ul>
            """).format(
                _('Disabled'),
                reason,
            )
            self.message_post(
                body=body,
                message_type='notification',
                body_is_html=True)
        return super().action_disable(reason)
