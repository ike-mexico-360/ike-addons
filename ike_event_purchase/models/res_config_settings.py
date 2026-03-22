from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    x_time_for_automatic_purchase_generation = fields.Integer(
        related='company_id.x_time_for_automatic_purchase_generation',
        string="Time for automatic purchase generation",
        help="Waiting time to automatically approve the quote",
        readonly=False)
