from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_events_allow_assistview = fields.Boolean(
        string='Open Assistview',
        default=True,
        tracking=True,
    )
