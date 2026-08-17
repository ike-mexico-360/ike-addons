from odoo import fields, models


class HelpdeskStages(models.Model):
    _inherit = 'helpdesk.stages'

    x_max_wait_time_minutes = fields.Integer(
        string='Max Wait Time (minutes)',
        default=0,
    )
