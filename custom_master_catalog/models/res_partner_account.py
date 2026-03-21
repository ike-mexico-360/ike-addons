# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === ACCOUNT FIELDS === #
    x_account_did = fields.Char(string='DID', tracking=True)
    x_account_type_id = fields.Many2one(
        comodel_name='custom.account.type',
        string='Account Type',
        tracking=True)
    x_account_identification_id = fields.Many2one(
        comodel_name='custom.account.identification',
        string='Account Identification',
        tracking=True)
    x_account_responsible_id = fields.Many2one(
        'hr.employee', "Account Responsible",
        tracking=True)

    @api.constrains('name', 'x_is_account', 'company_type', 'is_company')
    def _constrains_check_unique_account_record(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('x_is_account', '=', True),
                ('company_type', '=', 'company'),
                ('is_company', '=', True),
                ('id', '<>', rec.id),
            ]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_("A account with the same name already exists."))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_("A account with the same name already exists. It is disabled."))
