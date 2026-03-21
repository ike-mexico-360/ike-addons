from odoo import models, fields


class IkeEventServiceCountDetail(models.Model):
    _inherit = 'ike.event.service.count.detail'

    total_events = fields.Integer(  # Consultado a por api
        readonly=True, help="Total events of the subservice")
    x_saved_external_totals = fields.Boolean(
        string="Saved external totals", default=False, readonly=True,
        help="Technical: Flag to check if this line already has total data queried in the external API")
