from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomConsolidationMonthDay(models.Model):
    _name = 'custom.consolidation.month.day'
    _description = 'Custom Consolidation Month Day'
    _order = 'day asc'
    _rec_name = 'name'

    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        index=True)
    day = fields.Integer(
        string='Day',
        required=True,
        help='Allowed day of month for consolidation.')
    active = fields.Boolean(
        string='Active',
        default=True)

    @api.depends('day')
    def _compute_name(self):
        for record in self:
            record.name = str(record.day) if record.day else ''

    @api.constrains('day')
    def _check_day_constraints(self):
        for record in self:
            if not record.day:
                continue

            if record.day < 1 or record.day > 31:
                raise ValidationError(_('The day must be between 1 and 31.'))

            duplicate = self.search_count([
                ('id', '!=', record.id),
                ('day', '=', record.day),
                ('active', 'in', [True, False]),
            ])
            if duplicate:
                raise ValidationError(_('Day %s is already defined.') % record.day)
