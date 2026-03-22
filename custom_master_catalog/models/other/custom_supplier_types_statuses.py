# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomSupplierTypesStatuses(models.Model):
    _name = 'custom.supplier.types.statuses'
    _description = 'Types Of Supplier Statuses'
    _inherit = ['mail.thread']

    # === FIELDS ===
    active = fields.Boolean('Active', default=True, tracking=True)
    ref = fields.Char('')
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    name = fields.Char('Name', required=True, tracking=True)
    description = fields.Text('Description', size=300, tracking=True)
    affects_costs = fields.Boolean('Affects costs', default=False, tracking=True)

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
