# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === SUPPLIER FIELDS === #
    x_supplier_type_id = fields.Many2one(
        comodel_name='custom.supplier.type',
        string='Supplier Type',
        tracking=True)
    x_payment_type_id = fields.Many2one(
        comodel_name='custom.payment.type',
        string='Payment Type',
        tracking=True)

    x_supplier_center_ids = fields.One2many(
        'res.partner', 'parent_id',
        domain=[('type', '=', 'center')],
        string='Supplier Centers')

    x_geographical_area_ids = fields.One2many(
        'custom.geographical.area', 'partner_id',
        string='Geographical Coverage Areas',
        tracking=True)

    x_allowed_product_ids = fields.Many2many(
        'product.product', 'Allowed Sub-Services Ids',
        compute='_compute_allowed_product_ids',
        store=False
    )

    @api.depends('parent_id')
    def _compute_allowed_product_ids(self):
        for rec in self:
            supplier: int = rec.parent_id.id or rec.id
            coverage_id = self.env['custom.supplier.coverage.configuration'].search([
                ('supplier_id', '=', supplier),
            ], limit=1)

            allowed_product_ids = []
            if coverage_id:
                allowed_product_ids = coverage_id.mapped('supplier_coverage_config_line_ids.product_id.id')

            rec.x_allowed_product_ids = allowed_product_ids

    @api.constrains('name', 'x_is_supplier', 'company_type', 'is_company')
    def _constrains_check_unique_supplier_record(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('x_is_supplier', '=', True),
                ('company_type', '=', 'company'),
                ('is_company', '=', True),
                ('id', '<>', rec.id),
            ]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_("A supplier with the same name already exists."))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_("A supplier with the same name already exists. It is disabled."))
