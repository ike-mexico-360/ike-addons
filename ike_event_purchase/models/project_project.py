# -*- coding: utf-8 -*-

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = 'project.project'

    x_purchase_order_sequence_id = fields.Many2one(
        comodel_name='ir.sequence',
        string='Secuencia de órdenes de compra',
        copy=False,
        domain="[('x_available_for_project_purchase_orders', '=', True)]",
        help='Secuencia nativa de Odoo que se usará para numerar las órdenes de compra de este proyecto.',
    )
    x_ref_app = fields.Char(
        string='Reference app',
        help='Code of the application that created this project',
    )
