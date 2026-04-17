from odoo import models, fields, api


class IkeEventSupplierDefaultComment(models.Model):
    _name = 'ike.event.default.supplier_comment'
    _description = 'Event Binnacle Supplier Log'

    name = fields.Char(string='Comment', required=True, translate=True)
    disabled = fields.Boolean(string='Disabled', default=False)

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            domain = [('name', '=', rec.name), ('id', '!=', rec.id)]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValueError('The comment of the record already exists')
            if self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValueError('The comment of the record already exists. It is disabled')
