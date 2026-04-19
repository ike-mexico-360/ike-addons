# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class IkeEventProduct(models.Model):
    _name = 'ike.event.product'
    _description = 'Event Concept'
    _order = 'sequence, id'

    event_id = fields.Many2one('ike.event', required=True)
    supplier_number = fields.Integer(default=1, required=True)

    sequence = fields.Integer(default=1050)
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
    base = fields.Boolean(default=False)
    covered = fields.Boolean(default=False)
    mandatory = fields.Boolean(help='Can not be removed', default=False)
    is_manual = fields.Boolean(default=False)
    display_type = fields.Selection(
        selection=[
            ('line_section', "Section"),
            ('line_note', "Note"),
        ], default=False)

    event_supplier_number = fields.Integer(related='event_id.supplier_number', string='Event Supplier Number', readonly=True)

    # === ONCHANGES === #
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self._set_fields_onchange_product_id()
        else:
            self.covered = False
            self.mandatory = False
            self.base = False

    def _set_fields_onchange_product_id(self):
        # Base/Covered/Mandatory
        self.set_is_base()
        self.set_is_covered()
        if self.event_id._is_base_supplier():
            self.mandatory = self.base

        # Sequence
        current_siblings = self.event_id.service_product_ids.filtered(
            lambda x:
                x.id != self.id and x._origin
                and x.supplier_number == self.supplier_number
                and not x.display_type
        )
        sequences = current_siblings.filtered(lambda x: x.covered == self.covered).mapped('sequence')
        self.sequence = max(sequences, default=1 if self.covered else 1001) + 1

    # === COMPUTES === #
    @api.depends('product_id')
    def _compute_product_domain(self):
        for rec in self:

            domain = [
                ('sale_ok', '=', False),
                ('sh_product_subscribe', '=', False),
                ('purchase_ok', '=', True),
                ('x_concept_ok', '=', True),
                ('type', '=', 'service'),
                ('disabled', '=', False),
                ('list_price', '=', 0),
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

    # === SET METHODS === #
    def set_is_covered(self, no_update=False):
        for rec in self:
            if not rec.product_id or no_update and rec.covered:
                continue
            # Not supplier base then is not covered
            if rec.event_id.base_supplier_number != rec.supplier_number:
                continue

            plan_product_ids = (
                rec.event_id.user_membership_id.membership_plan_id
                .product_line_ids.filtered(
                    lambda x:
                        x.service_id.id == rec.event_id.service_id.id
                        and rec.event_id.sub_service_id.id in x.sub_service_ids.ids
                ).mapped('detail_ids.product_id.id')
            )
            rec.covered = rec.product_id.id in plan_product_ids

    def set_is_base(self, no_update=False):
        for rec in self:
            if not rec.product_id or no_update and rec.base:
                continue
            concept_line_id = rec.event_id.sub_service_id.concept_line_ids.filtered(
                lambda x:
                    not x.disabled
                    and x.base_concept_id.id == rec.product_id.id
                    and x.event_type_id.id == rec.event_id.event_type_id.id
            )

            rec.base = True if concept_line_id else False

    # === OVERRIDE === #
    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('from_internal', False):
            res.set_is_base()
            res.set_is_covered()
        return res


class IkeEventSupplierProduct(models.Model):
    _name = 'ike.event.supplier.product'
    _inherit = ['ike.event.product']
    _description = 'Event Supplier Product'

    event_supplier_link_id = fields.Many2one('ike.event.supplier.link', 'Event Supplier', required=True, ondelete='cascade')
    supplier_id = fields.Many2one(string='Supplier', related='event_supplier_link_id.supplier_id', store=True, readonly=True)
    event_id = fields.Many2one(related='event_supplier_link_id.event_id')

    # === AMOUNT FIELDS === #
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

    # Base fields
    cost_matrix_line_id = fields.Many2one('custom.supplier.cost.matrix.line', ondelete='set null')
    base_unit_price = fields.Float('Agreement Unit Price', default=0.0)
    base_cancel_price = fields.Float('Agreement Cancel Cost', default=0.0)
    base_cost_price = fields.Float('Agreement Cost', compute='_compute_base_amount', store=True)
    base_vat = fields.Float('Agreement Vat', compute='_compute_base_amount', store=True)
    base_subtotal = fields.Float('Agreement Subtotal', compute='_compute_base_amount', store=True)
    parent_product_id = fields.Many2one('product.product')

    # === AUTHORIZATION FIELDS === #
    authorization_pending = fields.Boolean(default=True)
    authorization_ids = fields.One2many(
        'ike.event.supplier.product.authorization', 'event_supplier_product_id',
        string='Authorizations')
    authorization_id = fields.Many2one(
        'ike.event.supplier.product.authorization',
        compute='_compute_authorization_id', store=True,
        string='Authorization')
    type_authorization_id = fields.Many2one(related='authorization_id.event_authorization_id.type_authorization_id', store=True)
    authorizer_name = fields.Char(related='authorization_id.event_authorization_id.authorizer', string='Authorized', store=True)

    product_add_domain = fields.Binary(compute='_compute_product_add_domain')

    from_portal = fields.Boolean(default=False, readonly=True)

    # === ONCHANGES === #
    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self._set_fields_onchange_product_id()
        else:
            self.covered = False
            self.mandatory = False
            self.base = False
            self.tax_ids = False
            self.base_unit_price = 0
            self.base_cancel_price = 0

    def _set_fields_onchange_product_id(self):
        # Covered/Base/Mandatory/Sequence
        super()._set_fields_onchange_product_id()
        # Prices
        self.set_base_prices()
        for rec in self:
            # Taxes
            rec.tax_ids = rec.product_id.taxes_id
            # Unit Price
            rec.unit_price = rec.base_unit_price

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

    @api.depends('quantity', 'base_unit_price', 'tax_ids')
    def _compute_base_amount(self):
        for rec in self:
            if not rec.is_net:
                base_cost = rec.quantity * rec.base_unit_price

                base_tax_amount = 0.0
                if rec.tax_ids:
                    taxes = rec.tax_ids.compute_all(rec.base_unit_price, quantity=rec.quantity)
                    base_tax_amount = sum(t['amount'] for t in taxes['taxes'])

                base_vat = base_tax_amount
                base_subtotal = base_cost + base_vat

                rec.base_cost_price = base_cost
                rec.base_vat = base_vat
                rec.base_subtotal = base_subtotal

    @api.depends('authorization_ids')
    def _compute_authorization_id(self):
        for rec in self:
            if rec.authorization_ids:
                rec.authorization_id = rec.authorization_ids[0].id
            else:
                rec.authorization_id = None

    @api.depends('product_id')
    def _compute_product_add_domain(self):
        for rec in self:
            domain = [
                ('active', '=', True),
                ('disabled', '=', False),
                ('x_additional_ok', '=', True),
                '|',
                ('x_apply_all_services_subservices', '=', True),
                ('x_categ_id', 'in', [rec.event_id.service_id.id, False]),
                '|',
                ('x_product_id', 'in', [rec.event_id.sub_service_id.id, False]),
                ('x_product_id', '=', False),
            ]

            if rec.event_id:
                # print(rec.event_supplier_link_id.event_id)
                excluded = rec.event_supplier_link_id.supplier_product_ids.filtered(
                    lambda x:
                        x.id != rec.id
                        and x.supplier_number == rec.supplier_number
                ).mapped('product_id.id')

                if excluded:
                    domain.append(('id', 'not in', excluded))

            rec.product_add_domain = domain

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

    # === SET METHODS === #
    def set_base_prices(self):
        for rec in self:
            if not rec.product_id:
                continue
            base_unit_price, base_cancel_price = rec.event_supplier_link_id.get_product_cost(rec.product_id.id)
            rec.base_unit_price = base_unit_price
            rec.base_cancel_price = base_cancel_price

    # === OVERRIDE === #
    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        if not self.env.context.get('from_internal', False):
            res.set_base_prices()
            if not res.unit_price:
                res.unit_price = res.base_unit_price
        return res

    def write(self, vals):
        if not vals.get('authorization_pending', False) and 'subtotal' in vals and vals['subtotal'] > self.subtotal:
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
