from odoo import models, fields, api, _


class IkeEventManualSupplierWizard(models.TransientModel):
    _name = 'ike.event.manual.supplier.wizard'
    _description = 'Event Manual Supplier Wizard'

    event_id = fields.Many2one(
        'ike.event',
        required=True,
        readonly=True)
    supplier_id = fields.Many2one(
        'res.partner',
        required=True,
        string='Supplier',
        domain="[('x_is_supplier', '=', True)]")
    supplier_phone = fields.Char(
        related='supplier_id.phone',
        string='Phone', readonly=True)
    truck_id = fields.Many2one(
        'fleet.vehicle',
        required=True,
        string='Town Truck')
    truck_domain = fields.Binary(
        string='Truck domain',
        compute='_compute_truck_domain')
    x_center_id = fields.Char(
        related='truck_id.x_center_id.name',
        string='Supplier Center',
        readonly=True,)

    # === COMPUTE METHODS === #
    @api.depends('event_id', 'supplier_id')
    def _compute_truck_domain(self):
        for rec in self:
            domain = [
                ('disabled', '=', False),
                ('x_vehicle_service_state', '=', 'available')
            ]

            if rec.supplier_id:
                domain.append(('x_partner_id', '=', rec.supplier_id.id))

            if rec.event_id:
                trucks_used = rec.event_id.service_supplier_ids.mapped('truck_id').ids
                if trucks_used:
                    domain.append(('id', 'not in', trucks_used))

            rec.truck_domain = domain

    # === ONCHANGE METHODS === #
    @api.onchange('supplier_id')
    def _onchange_supplier_id(self):
        if self.truck_id and self.truck_id.x_partner_id != self.supplier_id:
            self.truck_id = False

    @api.onchange('truck_id')
    def _onchange_truck_id(self):
        self.supplier_id = self.truck_id.x_partner_id

    # === ACTIONS === #
    def action_confirm(self):
        self.ensure_one()
        self.event_id.add_manual_suppliers_wizard(self.supplier_id, self.truck_id)
        return {'type': 'ir.actions.act_window_close'}
