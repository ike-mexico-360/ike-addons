# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomMetropolitanZone(models.Model):
    _name = 'custom.metropolitan.zone'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Metropolitan zone'

    name = fields.Char(required=True, tracking=True)
    municipality_ids = fields.Many2many(
        'custom.state.municipality',
        string='Municipalities',
        tracking=True
    )
    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False)

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
