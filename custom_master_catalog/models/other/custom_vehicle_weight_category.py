# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomVehicleWeightCategory(models.Model):
    _name = 'custom.vehicle.weight.category'
    _description = 'Weight Category Vehicles'
    _inherit = ['mail.thread']

    # === FIELDS === #
    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    name = fields.Char(string='Name', required=True, tracking=True)

    # === CONSTRAINT METHODS === #
    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('id', '!=', rec.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_('A record with the same name already exists.'))
