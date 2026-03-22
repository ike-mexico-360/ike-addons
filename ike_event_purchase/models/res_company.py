from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_time_for_automatic_purchase_generation = fields.Integer(
        string="Time for automatic purchase generation", default=72,
        help="Waiting time to automatically approve the quote")
