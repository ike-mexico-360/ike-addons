# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === ACCOUNT FIELDS === #
    x_account_did = fields.Char(string='DID', tracking=True)
    x_validation_pattern = fields.Char(string='Validation pattern', tracking=True)
    x_display_mask = fields.Char(string='Display mask', tracking=True)
    x_validation_pattern_second = fields.Char(string='Second validation pattern', tracking=True)
    x_display_mask_second = fields.Char(string='Second display mask', tracking=True)
    x_validation_clause_patter = fields.Char(string="Clause validation pattern.")
    x_validation_second_clause_patter = fields.Char(string="Second clause validation pattern")
    x_account_type_id = fields.Many2one(
        comodel_name='custom.account.type',
        string='Account Type',
        domain="[('active', '=', True), ('disabled', '=', False)]",
        tracking=True)
    x_account_identification_id = fields.Many2one(
        comodel_name='custom.account.identification',
        string='Account Identification',
        domain="[('id', '!=', x_second_key_identification_id), ('disabled', '=', False), ('active', '=', True)]",
        tracking=True)
    x_check_second_key = fields.Boolean(string="Do you have a second key?")
    x_second_key_identification_id = fields.Many2one(
        comodel_name='custom.account.identification',
        string='Second identifier',
        domain="[('id', '!=', x_account_identification_id), ('disabled', '=', False)]",
        tracking=True)
    x_clause_required = fields.Boolean(string="Clause required")
    x_second_clause_required = fields.Boolean(string="Second clause required")
    authorizer = fields.Boolean(string="Authorization")
    x_account_responsible_id = fields.Many2one(
        'hr.employee', "Account Responsible",
        tracking=True)
    x_is_policy_account = fields.Boolean(
        compute='_compute_is_policy_account',
        store=False
    )
    x_is_policy_second_account_second = fields.Boolean(
        compute='_compute_is_policy_second_account',
        store=False
    )

    @api.constrains('name', 'x_is_account', 'company_type', 'is_company')
    def _constrains_check_unique_account_record(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('x_is_account', '=', True),
                ('is_company', '=', True),
                ('id', '<>', rec.id),
            ]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_("A account with the same name already exists."))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_("A account with the same name already exists. It is disabled."))

    # === ONCHANGE === #
    @api.onchange('x_account_identification_id')
    def _onchange_x_account_identification_id(self):
        if self.x_account_identification_id:
            self.x_validation_pattern = self.x_account_identification_id.regex

    @api.onchange('x_account_identification_id', 'x_second_key_identification_id')
    def _onchange_identification(self):
        domain = {}

        # Si ambos son iguales → limpiar el segundo
        if (
            self.x_account_identification_id
            and self.x_second_key_identification_id
            and self.x_account_identification_id == self.x_second_key_identification_id
        ):
            self.x_second_key_identification_id = False

        return {'domain': domain}

    @api.onchange('parent_id')
    def _onchange_parent_id_colony(self):
        if self.parent_id and self.x_is_account and self.is_company and self.company_type == 'company':
            self.l10n_mx_edi_colony = self.parent_id.l10n_mx_edi_colony

    @api.depends('x_account_identification_id')
    def _compute_is_policy_account(self):
        policy = self.env.ref('custom_master_catalog.account_identification_policy')
        for rec in self:
            rec.x_is_policy_account = (
                rec.x_account_identification_id == policy
            )

    @api.depends('x_second_key_identification_id')
    def _compute_is_policy_second_account(self):
        policy = self.env.ref('custom_master_catalog.account_identification_policy')
        for rec in self:
            rec.x_is_policy_second_account_second = (
                rec.x_second_key_identification_id == policy
            )
