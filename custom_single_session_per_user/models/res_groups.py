from odoo import models, fields


class ResGroups(models.Model):
    _inherit = 'res.groups'

    exclude_single_session = fields.Boolean(
        string="Exclude Single Session",
        help="If checked, members of this group will not be restricted to a single session."
    )
