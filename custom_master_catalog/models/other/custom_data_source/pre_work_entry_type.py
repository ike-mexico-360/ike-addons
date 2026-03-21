# -*- coding: utf-8 -*-

from odoo import api, fields, models  # , _
# from odoo.exceptions import UserError


class CustomPreWorkEntryType(models.Model):
    _name = 'custom.pre.work.entry.type'
    _description = 'Pre-Work Entry Type'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    external_code = fields.Char()
    sequence = fields.Integer(default=25)
    parent_id = fields.Many2one('custom.pre.work.entry.type')
    color = fields.Integer(default=0)
    value_type = fields.Selection([
        ('amount', 'Amount'),
        ('qty', 'Quantity'),
    ], default='amount', required=True)
    is_totalizing = fields.Boolean('Totalizing', default=False)
    active = fields.Boolean('Active', default=True,)
    country_id = fields.Many2one('res.country', string="Country", default=lambda self: self.env.company.country_id)
    country_code = fields.Char(related='country_id.code')
    exclude_in_output_file = fields.Boolean('Exclude in output file', default=False)

    @api.depends('name', 'code')
    def _compute_display_name(self):
        for entry in self:
            if entry.code:
                name = f"[{entry.code}] {entry.name}"
            else:
                name = f"{entry.name}"
            entry.display_name = name

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if args is None:
            args = []
        entries = self.search([('code', operator, name)] + args, limit=limit)
        if not entries:
            return super().name_search(name, args, operator, limit)
        return entries.name_get()
