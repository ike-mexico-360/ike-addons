# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === CONSTRAINT METHODS === #
    @api.constrains('name', 'x_is_ike', 'company_type', 'is_company')
    def _constrains_check_unique_company_ike_record(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('x_is_ike', '=', True),
                ('is_company', '=', True),
                ('id', '<>', rec.id),
            ]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_("A company with the same name already exists."))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_("A company with the same name already exists. It is disabled."))
