from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomIncidentType(models.Model):
    _name = 'custom.incident.type'
    _description = 'Custom Incident Type'

    ref = fields.Char(string='Reference', required=True)
    name = fields.Char(string='Name', required=True, translate=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)

    @api.constrains('ref')
    def _check_ref(self):
        for rec in self:
            if rec.ref and not rec.ref.isalnum():
                raise ValidationError(_('Reference must be alphanumeric.'))
            exist_records = self.search_count([('ref', '=', rec.ref), ('company_id', '=', rec.company_id.id)])
            if exist_records > 1:
                raise ValidationError(_('Reference must be unique.'))
