# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomHolidays(models.Model):
    _name = 'custom.holidays'
    _description = 'Account Type'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    year = fields.Integer(tracking=True, digits=4)
    date = fields.Date(required=True, tracking=True)

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

    @api.constrains('date', 'year', 'active', 'disabled')
    def _check_unique_date_year_active(self):
        for record in self:
            if record.active and not record.disabled:
                if record.date and record.year:
                    existing = self.search([
                        ('date', '=', record.date),
                        ('year', '=', record.year),
                        ('active', '=', True),
                        ('disabled', '=', False),
                        ('id', '!=', record.id)
                    ])
                    if existing:
                        raise ValidationError(_(
                            f"There is already an ACTIVE record with the combination of "
                            f"Date {record.date} and Year {record.year}.")
                        )

    @api.onchange('year')
    def _onchange_year(self):
        if self.year:
            if self.year < 2000 or self.year > 9999:
                self.year = 0
                return {
                    'warning': {
                        'title': "Invalid year",
                        'message': _('The year must have exactly 4 digits and be greater than 2000'),
                    }
                }
