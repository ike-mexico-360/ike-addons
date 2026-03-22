# -*- coding: utf-8 -*-
from odoo import models, fields  # , api, _


class CustomProductMapping(models.Model):
    _name = 'custom.product.mapping'
    _description = 'Custom Product Mapping'
    _order = 'parent_id, product_id'
    _rec_name = 'product_id'

    parent_id = fields.Many2one('product.product', required=True)
    product_id = fields.Many2one('product.product', required=True)
    product_default_code = fields.Char(related='product_id.default_code')
    categ_id = fields.Many2one('product.category', related='product_id.categ_id', string="Service")
    active = fields.Boolean(default=True)

    _sql_constraints = [(
        'product_uniq',
        "unique(parent_id, product_id)",
        "Product must be unique."
    )]
