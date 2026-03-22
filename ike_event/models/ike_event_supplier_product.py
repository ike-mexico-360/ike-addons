# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class IkeEventProduct(models.Model):
    _name = 'ike.event.product'
    _description = 'Event Concept'

    event_id = fields.Many2one('ike.event', required=True)
    supplier_number = fields.Integer(default=1, required=True)

    sequence = fields.Integer(default=500)
    name = fields.Text(string='Description')
    product_id = fields.Many2one('product.product', string='Concept')
    product_domain = fields.Binary(compute='_compute_product_domain')
    uom_id = fields.Many2one(
        'uom.uom',
        string='UoM',
        related='product_id.uom_id',
        store=True,
        readonly=True)
    estimated_quantity = fields.Integer(default=1)
    covered = fields.Boolean(default=False)
    mandatory = fields.Boolean(help='Can not be removed', default=False)
    is_manual = fields.Boolean(default=False)
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ], default=False)

    event_supplier_number = fields.Integer(related='event_id.supplier_number', string='Event Supplier Number')

    # === COMPUTES === #
    @api.depends('product_id')
    def _compute_product_domain(self):
        for rec in self:

            domain = [
                ('sale_ok', '=', False),
                ('sh_product_subscribe', '=', False),
                ('purchase_ok', '=', True),
                ('x_accessory_ok', '=', False),
                ('type', '=', 'service'),
                ('disabled', '=', False),
                ('list_price', '=', 0),
                ('standard_price', '=', 0),
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
                ('x_categ_id', 'in', [rec.event_id.service_id.id, False]),
                '|',
                ('x_product_id', 'in', [rec.event_id.sub_service_id.id]),
                ('x_product_id', '=', False),
            ]

            if rec.event_id:
                excluded = rec.event_id.service_product_ids.filtered(
                    lambda x:
                        x.id != rec.id
                        and x.supplier_number == rec.supplier_number
                ).mapped('product_id.id')
                if excluded:
                    domain.append(('id', 'not in', excluded))

            rec.product_domain = domain


class IkeEventSupplierProduct(models.Model):
    _name = 'ike.event.supplier.product'
    _inherit = ['ike.event.product']
    _description = 'Event Supplier Product'

    event_supplier_link_id = fields.Many2one('ike.event.supplier.link', 'Event Supplier', required=True, ondelete='cascade')
    supplier_id = fields.Many2one(string='Supplier', related='event_supplier_link_id.supplier_id', store=True, readonly=True)
    event_id = fields.Many2one(related='event_supplier_link_id.event_id')

    # === AMOUNT FIELDS === #
    base_unit_price = fields.Float('Agreement Cost', default=0.0)
    base_cancel_price = fields.Float('Agreement Cancel Cost', default=0.0)

    unit_price = fields.Float('Unit Cost', default=0.0)
    quantity = fields.Integer(default=1)
    is_net = fields.Boolean('Net?', default=False)
    tax_ids = fields.Many2many(
        'account.tax',
        'ike_event_supplier_product_tax',
        string='Taxes')
    cost_price = fields.Float('Cost', compute="_compute_amount", store=True)  # Without taxes
    vat = fields.Float('VAT', compute="_compute_amount", store=True)
    subtotal = fields.Float('Subtotal', compute="_compute_amount", store=True)

    cost_matrix_line_id = fields.Many2one('custom.supplier.cost.matrix.line', ondelete='set null')

    # === AUTHORIZATION FIELDS === #
    authorization_pending = fields.Boolean(default=False)
    authorization_ids = fields.One2many(
        'ike.event.supplier.product.authorization', 'event_supplier_product_id',
        string='Authorizations')
    authorization_id = fields.Many2one(
        'ike.event.supplier.product.authorization',
        compute='_compute_authorization_id', store=True,
        string='Authorization')
    type_authorization_id = fields.Many2one(related='authorization_id.event_authorization_id.type_authorization_id', store=True)
    authorizer_name = fields.Char(related='authorization_id.event_authorization_id.authorizer', string='Authorized', store=True)

    # === COMPUTES === #
    @api.depends('quantity', 'unit_price', 'tax_ids')
    def _compute_amount(self):
        for rec in self:
            if not rec.is_net:
                cost = rec.quantity * rec.unit_price

                tax_amount = 0.0
                if rec.tax_ids:
                    taxes = rec.tax_ids.compute_all(rec.unit_price, quantity=rec.quantity)
                    tax_amount = sum(t['amount'] for t in taxes['taxes'])

                vat = tax_amount
                subtotal = cost + vat

                rec.cost_price = cost
                rec.vat = vat
                rec.subtotal = subtotal

    @api.depends('authorization_ids')
    def _compute_authorization_id(self):
        for rec in self:
            if rec.authorization_ids:
                rec.authorization_id = rec.authorization_ids[0].id
            else:
                rec.authorization_id = None

    # === METHODS ONCHANGE === #
    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                # Taxes
                rec.tax_ids = rec.product_id.taxes_id
                # Cost
                base_unit_price, base_cancel_price = self.event_supplier_link_id.get_product_cost(rec.product_id.id)
                rec.base_unit_price = base_unit_price
                rec.base_cancel_price = base_cancel_price
                rec.unit_price = base_unit_price
            else:
                rec.tax_ids = False

    # === ACTIONS === #
    def action_view_matrix_cost_lines(self):
        self.ensure_one()
        # Filter Ids
        municipality_id = self.env['custom.state.municipality'].search([
            ('disabled', '=', False),
            ('code_ids', 'like', self.event_id.location_zip_code)
        ], limit=1)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vehicles',
            'res_model': 'custom.supplier.cost.matrix.line',
            'view_mode': 'list',
            'target': 'new',
            'domain': [
                ('supplier_center_id.parent_id', '=', self.supplier_id.id),
                ('concept_id', '=', self.product_id.id),
                ('subservice_id', '=', self.event_id.sub_service_id.id),
                ('type_event_id', '=', self.event_id.event_type_id.id),
                ('vehicle_category_id', '=', 'Auto'),
                ('supplier_status_id.ref', '=', 'concluded'),
                '|',
                ('account_id', '=', False),
                ('account_id', '=', self.event_id.user_membership_id.membership_plan_id.account_id.id),
                '|',
                ('geographical_area_id', '=', False),
                ('geographical_area_id', '=', municipality_id.id),
            ],
            'context': {
                'order_by': 'state_id, municipality_id, date_init desc, date_end',
            }
        }

    # === OVERRIDE === #
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('display_type', None) and ('base_unit_price' not in vals or 'unit_price' not in vals):
                event_supplier_link_id = self.env['ike.event.supplier.link'].sudo().browse(vals['event_supplier_link_id'])
                base_unit_price, base_cancel_price = event_supplier_link_id.sudo().get_product_cost(vals['product_id'])
                vals['base_unit_price'] = base_unit_price
                vals['base_cancel_price'] = base_cancel_price

                if vals.get('unit_price', None) in (None, 0) and base_unit_price:
                    vals['unit_price'] = base_unit_price

        return super().create(vals_list)

    def write(self, vals):
        if not self.env.context.get('ignore_authorization'):
            quantity = vals.get('quantity', self.quantity)
            unit_price = vals.get('unit_price', self.unit_price)
            if quantity > self.quantity or unit_price > self.unit_price:
                vals['authorization_pending'] = True
        return super().write(vals)


class IkeEventSupplierProductAuthorization(models.Model):
    _name = 'ike.event.supplier.product.authorization'
    _description = 'Event Supplier Product Authorization'
    _order = 'id desc'

    event_supplier_product_id = fields.Many2one('ike.event.supplier.product', ondelete='cascade', required=True, readonly=True)
    event_authorization_id = fields.Many2one('ike.event.authorization', ondelete='cascade', required=True, readonly=True)
    quantity = fields.Float(default=1, readonly=True)
    unit_price = fields.Float('Unit Cost', readonly=True)
    amount = fields.Float(readonly=True)
