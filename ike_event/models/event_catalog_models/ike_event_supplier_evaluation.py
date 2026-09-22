
from odoo import models, fields, api, _


class IkeEventSupplierEvaluation(models.Model):
    _name = 'ike.event.supplier.evaluation'
    _description = 'Event Supplier Evaluation'

    name = fields.Char(translate=True, required=True)
    sequence = fields.Char(default=5)

    reevaluation = fields.Boolean(default=True)

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False)
