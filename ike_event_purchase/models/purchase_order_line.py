from odoo import api, models, fields, _
from odoo.exceptions import UserError


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    x_generated_from_event = fields.Boolean('Technical: Generated from event', default=False, copy=False)
    x_has_dispute_changes = fields.Boolean('Technical: Has dispute changes', default=False, copy=False)

    # Link to ike.event.supplier.product, if not value, has manual cost
    x_supplier_product_id = fields.Many2one(
        'ike.event.supplier.product', 'Supplier Product', copy=False,
        help="Technical: Link to event concept product")

    x_concept_line_id = fields.Many2one(
        'custom.membership.plan.product.line', 'Concept Line', copy=False,
        help="Technical: Link to membership plan concept line")

    # Original fields
    price_unit = fields.Float(sub_tracking=True)
    product_qty = fields.Float(sub_tracking=True)
    # Dispute
    x_price_unit_dispute = fields.Float('Dispute Price', copy=False, sub_tracking=True)
    x_product_qty_dispute = fields.Float('Dispute Quantity', copy=False, sub_tracking=True)
    x_price_subtotal_dispute = fields.Monetary(compute='_x_compute_amount_dispute', string='Subtotal dispute', aggregator=None, store=True)
    # Approved
    x_price_unit_approved = fields.Float('Approved Price', copy=False, sub_tracking=True)
    x_product_qty_approved = fields.Float('Approved Quantity', copy=False, sub_tracking=True)
    x_price_subtotal_approved = fields.Monetary(compute='_x_compute_amount_approved', string='Subtotal approved', aggregator=None, store=True)
    # Event values
    x_price_unit_event = fields.Float('Event Price', related='x_supplier_product_id.cost_price')
    x_product_qty_event = fields.Integer('Event Quantity', related='x_supplier_product_id.quantity')
    x_price_subtotal_event = fields.Monetary(compute='_x_compute_amount_event', string='Subtotal event', aggregator=None, store=True)

    @api.depends('x_product_qty_dispute', 'x_price_unit_dispute',)
    def _x_compute_amount_dispute(self):
        for line in self:
            line.x_price_subtotal_dispute = line.x_price_unit_dispute * line.x_product_qty_dispute

    @api.depends('x_product_qty_approved', 'x_price_unit_approved',)
    def _x_compute_amount_approved(self):
        for line in self:
            line.x_price_subtotal_approved = line.x_price_unit_approved * line.x_product_qty_approved

    @api.depends('x_product_qty_event', 'x_price_unit_event',)
    def _x_compute_amount_event(self):
        for line in self:
            line.x_price_subtotal_event = line.x_price_unit_event * line.x_product_qty_event

    def unlink(self):
        generated_lines_from_event = self.filtered(lambda line: line.x_generated_from_event)
        if generated_lines_from_event:
            raise UserError(_('You cannot delete generated lines from event'))
        return super().unlink()
