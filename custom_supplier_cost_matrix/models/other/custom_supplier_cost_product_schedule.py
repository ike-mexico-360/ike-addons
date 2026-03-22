from odoo import models, fields, api, _
from markupsafe import Markup
from odoo.exceptions import ValidationError


class CustomSupplierCostProductSchedules(models.Model):
    _name = 'custom.supplier.cost.product.schedule'
    _description = 'Custom Schedules'
    _inherit = ['mail.thread']

    _rec_name = 'name'

    name = fields.Char(string='Name', required=True, tracking=True, copy=False, translate=True)
    active = fields.Boolean(default=True, tracking=True, copy=False)
    disabled = fields.Boolean(default=False, tracking=True, copy=False)

    start_time = fields.Float('Start Time', tracking=True)
    end_time = fields.Float('End Time', tracking=True)

    # === CONSTRAINS === #
    @api.constrains('name')
    def _check_unique_schedules(self):
        for rec in self:
            domain = [('id', '<>', rec.id), ('name', '=', rec.name)]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_('A record with the same name already exists.'))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_('A record with the same name already exists. It is disabled.'))
