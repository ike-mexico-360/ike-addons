# -*- coding: utf-8 -*-

from odoo import fields, models


class IrSequence(models.Model):
    _inherit = 'ir.sequence'

    x_available_for_project_purchase_orders = fields.Boolean(
        string='Available for project purchase orders',
        help='Allows this sequence to be selected in project purchase settings.',
    )
