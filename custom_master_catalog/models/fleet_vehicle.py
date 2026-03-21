from odoo import models, fields, api, _
from odoo.exceptions import UserError
from markupsafe import Markup


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    x_partner_id = fields.Many2one('res.partner', 'Supplier', tracking=True, domain=[('x_is_supplier', '=', True), ('disabled', '=', False)])
    x_ref_supplier = fields.Char('Supplier reference', tracking=True)
    x_center_id = fields.Many2one('res.partner', 'Center of attention', tracking=True, domain=[('disabled', '=', False)])

    x_vehicle_ref = fields.Char('Supplier vehicle reference', tracking=True)
    x_vehicle_type = fields.Many2one('custom.vehicle.type', 'Custom Vehicle Type', tracking=True)
    x_product_category_id = fields.Many2one(
        'product.category', 'Service', related='x_vehicle_type.x_service_id', store=True, tracking=True)
    x_product_id = fields.Many2one(
        'product.product', 'Subservice', related='x_vehicle_type.x_subservice_id', store=True, tracking=True)
    x_federal_license_plates = fields.Boolean('Federal License Plates', tracking=True)
    subservice_specification_ids = fields.Many2many(
        'custom.subservice.specification',
        'subservice_specification_fleet_vehicle_rel',
        'fleet_vehicle_id',
        'subservice_specification_id',
        'Category specification',
        compute='_compute_subservice_specification_ids',
        domain="[('disabled', '=', False), ('service_id', '=', x_product_category_id)]",
        tracking=True
    )
    x_maneuvers = fields.Boolean('Maneuvers', tracking=True)
    x_accessories = fields.Many2many(
        'product.product', string='Accessories', tracking=True,
        domain=lambda self: self.env['product.product'].get_accessories_domain())
    x_vehicles_axes = fields.Integer(string="Ejes", tracking=True)
    x_manages_tire_conditioning = fields.Boolean('Manages Tire Conditioning', tracking=True)
    x_longitude = fields.Char(string='Longitude', tracking=True)
    x_latitude = fields.Char(string='Latitude', tracking=True)
    x_vehicle_service_state = fields.Selection([
        ('available', 'Available'),
        ('not_available', 'Not Available'),
        ('in_service', 'In Service'),
        ('disabled', 'Disabled'),
    ], string="Vehicle Service State", tracking=True, default="not_available")
    x_driver_domain = fields.Binary(string='Driver Domain', compute='_compute_x_driver_domain')

    @api.depends('driver_id', 'x_partner_id')
    def _compute_x_driver_domain(self):
        for vehicle in self:
            domain = []
            if vehicle.x_partner_id:
                self.env.cr.execute("""
                    SELECT partner_id AS id
                    FROM res_partner_supplier_users_rel
                    WHERE supplier_id = %s AND user_type = 'operator';
                """ % (vehicle.x_partner_id.id,))
                driver_ids = [x['id'] for x in self.env.cr.dictfetchall()]
                domain.append(('id', 'in', driver_ids))
            vehicle.x_driver_domain = domain

    @api.constrains('driver_id')
    def _check_unique_driver(self):
        for rec in self:
            if rec.driver_id and self._context.get('x_supplier_vehicles', False):
                vehicles = self.env['fleet.vehicle'].search_count([
                    ('driver_id', '=', rec.driver_id.id),
                    ('id', '!=', rec.id)
                ])
                if vehicles > 0:
                    raise UserError(_('Driver assigned to another vehicle'))

    @api.constrains('model_year')
    def _check_model_year(self):
        for rec in self:
            if rec.model_year:
                if not rec.model_year.isdigit():
                    raise UserError(_("Year must contain only numbers."))
                if len(rec.model_year) != 4:
                    raise UserError(_("Year must be 4 digits."))

    @api.depends('x_vehicle_type')
    def _compute_subservice_specification_ids(self):
        for vehicle in self:
            vehicle.subservice_specification_ids = [x.id for x in vehicle.x_vehicle_type.subservice_specification_ids]

    @api.constrains('x_vehicle_ref')
    def _check_x_vehicle_ref(self):
        for rec in self:
            domain = [('id', '!=', rec.id), ('x_vehicle_ref', '=', rec.x_vehicle_ref)]
            records_not_dissabled = self.search(domain + [('disabled', '=', False)])
            if records_not_dissabled:
                raise UserError(_('Vehicle already exists with this reference'))
            records_dissabled = self.search(domain + [('disabled', '=', True)])
            if records_dissabled:
                raise UserError(_('Vehicle already exists with this reference and is disabled'))

    def action_disable(self, reason=None):
        for rec in self:
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
                rec.message_post(
                    body=body,
                    message_type='notification',
                    body_is_html=True)
        return super().action_disable(reason)
