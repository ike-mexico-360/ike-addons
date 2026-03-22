
from odoo import models, fields, api, _


class IkeEventCancellationReason(models.Model):
    _name = 'ike.event.cancellation.reason'
    _description = 'Event cancellation reason'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Motive", tracking=True)
    sequence = fields.Char(default=5)
    show_supplier = fields.Boolean(string="Show supplier", tracking=True)

    active = fields.Boolean(default=True, tracking=True)
    disabled = fields.Boolean(default=False, tracking=True)

    _sql_constraints = [
        (
            'unique_name',
            'unique(name)',
            'The cancellation reason already exists.'
        )
    ]
