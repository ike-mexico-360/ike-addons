# -*- coding: utf-8 -*-
from odoo import models, fields


class CustomImportXmlInvoiceLine(models.Model):
    _name = 'custom.import.xml.invoice.line'
    _description = 'SAT XML Validator Line Detail'

    sat_line_id = fields.Many2one(
        'custom.sat.validator.line',
        string="SAT XML Validator Line Reference",
        ondelete='cascade',
        required=True
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        change_default=True,
        default=lambda self: self.env.company
    )

    company_currency_id = fields.Many2one(
        string='Company Currency',
        related='company_id.currency_id',
        readonly=True,
    )

    product_name = fields.Char(string="Product Name / Description", required=True)
    quantity = fields.Float(string="Quantity", digits=(16, 4), default=1.0)

    price_unit = fields.Monetary(
        string="Unit Price",
        currency_field='company_currency_id'
    )

    subtotal = fields.Monetary(
        string="Subtotal",
        currency_field='company_currency_id'
    )

    tax_ids = fields.Many2many(
        'account.tax',
        'custom_import_xml_inv_line_tax_rel',
        'line_id',
        'tax_id',
        string="XML Taxes"
    )

    purchase_order_line_ids = fields.Many2many(
        'purchase.order.line',
        'custom_import_xml_inv_line_po_line_rel',
        'xml_line_id',
        'po_line_id',
        string="Related Purchase Order Lines"
    )
