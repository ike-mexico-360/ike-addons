from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class IkeEventDuplicateReason(models.Model):
    _name = "ike.event.duplicate.reason"
    _description = "Motive duplicate"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char(string="Motive", tracking=True)

    active = fields.Boolean('Active', default=True, tracking=True)   
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if not rec.name:
                continue

            existing = self.search([
                ('id', '!=', rec.id),
                ('name', '=ilike', rec.name.strip())
            ], limit=1)

            if existing:
                raise ValidationError(_("The reason name must be unique."))