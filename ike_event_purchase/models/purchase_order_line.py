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
    x_product_qty_dispute = fields.Float('Dispute Quantity', copy=False, sub_tracking=True, default=1)
    x_price_subtotal_dispute = fields.Monetary(compute='_x_compute_amount_dispute', string='Subtotal dispute', aggregator=None, store=True)
    # Approved
    x_price_unit_approved = fields.Float('Approved Price', copy=False, sub_tracking=True)
    x_product_qty_approved = fields.Float('Approved Quantity', copy=False, sub_tracking=True, default=1)
    x_price_subtotal_approved = fields.Monetary(compute='_x_compute_amount_approved', string='Subtotal approved', aggregator=None, store=True)
    # Event values
    x_price_unit_event = fields.Float('Event Price', related='x_supplier_product_id.cost_price')
    x_product_qty_event = fields.Integer('Event Quantity', related='x_supplier_product_id.quantity')
    x_price_subtotal_event = fields.Monetary(compute='_x_compute_amount_event', string='Subtotal event', aggregator=None, store=True)

    x_parent_event_id = fields.Many2one('ike.event', 'Event', help="Techinical: Refer to the event of the purchase order")

    x_covered = fields.Boolean('Covered', default=False)
    x_mandatory = fields.Boolean('Mandatory', default=False)

    x_product_domain = fields.Binary(compute='_x_compute_product_domain')

    # === ONCHANGES === #
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self._x_set_fields_onchange_product_id()
        else:
            self.x_covered = False

    def _x_set_fields_onchange_product_id(self):
        # Covered
        self._x_set_is_covered()

        # Sequence
        current_siblings = self.order_id.order_line.filtered(
            lambda x:
                x.id != self.id and x._origin
                and not x.display_type
        )
        sequences = current_siblings.filtered(lambda x: x.x_covered == self.x_covered).mapped('sequence')
        self.sequence = max(sequences, default=1 if self.x_covered else 1001) + 1

    # === COMPUTES === #
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

    @api.depends('product_id', 'order_id.order_line.product_id')
    def _x_compute_product_domain(self):
        for rec in self:
            selected_product_ids = rec.order_id.order_line.filtered(
                lambda l: l.product_id and l.id != rec.id
            ).mapped('product_id').ids

            domain = [
                ('sale_ok', '=', False),
                ('sh_product_subscribe', '=', False),
                ('purchase_ok', '=', True),
                ('x_concept_ok', '=', True),
                ('type', '=', 'service'),
                ('disabled', '=', False),
                ('list_price', '=', 0),
                ('id', 'not in', selected_product_ids),
                ('uom_id', 'in', [
                    self.env.ref('uom.product_uom_km').id,
                    self.env.ref('uom.product_uom_day').id,
                    self.env.ref('uom.product_uom_hour').id,
                    self.env.ref('l10n_mx.product_uom_service_unit').id,
                    self.env.ref('uom.product_uom_unit').id,
                    self.env.ref('uom.product_uom_litre').id
                ]),
                '|',
                ('x_apply_all_services_subservices', '=', True),
                ('x_categ_id', 'in', [rec.order_id.x_event_id.service_id.id, False]),
                '|',
                ('x_product_id', 'in', [rec.order_id.x_event_id.sub_service_id.id]),
                ('x_product_id', '=', False),
            ]

            rec.x_product_domain = domain

    def unlink(self):
        generated_lines_from_event = self.filtered(lambda line: line.x_generated_from_event)
        if generated_lines_from_event:
            raise UserError(_('You cannot delete generated lines from event'))
        return super().unlink()

    # === SET METHODS === #
    def _x_set_is_covered(self, no_update=False):
        for rec in self:
            if not rec.product_id or no_update and rec.x_covered:
                continue

            plan_product_ids = (
                rec.sudo().order_id.x_event_id.user_membership_id.membership_plan_id
                .product_line_ids.filtered(
                    lambda x:
                        x.service_id.id == rec.sudo().order_id.x_event_id.service_id.id
                        and rec.sudo().order_id.x_event_id.sub_service_id.id in x.sub_service_ids.ids
                ).mapped('detail_ids.product_id.id')
            )
            rec.x_covered = rec.product_id.id in plan_product_ids

            # Sequence
            current_siblings = rec.order_id.order_line.filtered(
                lambda x:
                    x.id != rec.id
                    and x._origin
                    and not x.display_type
            )

            sequences = current_siblings.filtered(lambda x: x.x_covered == rec.x_covered).mapped('sequence')

            rec.sequence = max(sequences, default=1 if rec.x_covered else 1001) + 1

    def _x_set_unit_prices(self):
        for rec in self:
            if not rec.product_id or rec.order_id.x_event_id:
                continue

            matrix_lines = rec.sudo().order_id.x_event_id.get_supplier_product_matrix_lines(rec.order_id.partner_id.id, [rec.product_id.id])

            cost_line = matrix_lines.filtered(
                lambda x: x.concept_id.id == rec.product_id.id
                and x.supplier_status_id.ref == 'concluded'
            )

            rec.price_unit = cost_line[0].cost if cost_line else 0

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)

        lines = res.filtered(lambda r: r.order_id.x_event_id)
        if not self.env.context.get('ike_event_purchase', False) and lines:
            lines._x_set_is_covered()
            lines._x_set_unit_prices()

        return res

    def write(self, vals):
        update_covered = False

        if 'product_id' in vals:

            for line in self:
                if vals['product_id'] != line.product_id.id:
                    update_covered = True
                    break

        res = super().write(vals)

        if update_covered:
            self._x_set_is_covered()

        return res