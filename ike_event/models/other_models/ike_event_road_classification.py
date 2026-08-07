from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class IkeEventRoadClassification(models.Model):
    _name = 'ike.event.road.classification'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Help to road classification'

    name = fields.Char(string="Type", tracking=True)

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if not rec.name:
                continue

            existing = self.search([
                ('id', '!=', rec.id),
                ('name', '=ilike', rec.name.strip()),
            ], limit=1)

            if existing:
                raise ValidationError(
                    _("The name '%s' already exists. It must be unique.") % rec.name
                )
