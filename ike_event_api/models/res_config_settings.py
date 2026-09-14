from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    x_events_allow_assistview = fields.Boolean(
        string="Open Assistview",
        help="Enable assistview",
        groups="base.group_no_one",
        related='company_id.x_events_allow_assistview',
        readonly=False,
    )
