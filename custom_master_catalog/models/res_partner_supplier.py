# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === SUPPLIER FIELDS === #
    x_coverage_count = fields.Integer(
        string='Number of service and subservice configurations',
        compute='_compute_x_coverage_count',
        store=False
    )
    x_is_electronic = fields.Boolean(string='Electronics', tracking=True)
    x_is_manual = fields.Boolean(string='Manual', tracking=True)
    x_is_extraordinary = fields.Boolean(string='Extraordinary', tracking=True)
    x_is_special_accounts = fields.Boolean(
        string="Exclusivity to special accounts", tracking=True
    )
    x_is_exclusive_accounts = fields.Boolean(string="Exclusive accounts", tracking=True)
    x_supplier_type_id = fields.Many2one(
        comodel_name='custom.supplier.type',
        string='Supplier Type',
        tracking=True)
    x_payment_type_id = fields.Many2one(
        comodel_name='custom.payment.type',
        string='Payment Type',
        tracking=True)

    x_supplier_center_ids = fields.One2many(
        'res.partner', 'parent_id',
        domain=[('type', '=', 'center')],
        string='Supplier Centers')

    x_geographical_area_ids = fields.One2many(
        'custom.geographical.area', 'partner_id',
        string='Geographical Coverage Areas',
        tracking=True)

    x_geographical_area_supplier_ids = fields.One2many(
        comodel_name='custom.geographical.area',
        compute="_compute_geographical_area_supplier_ids",
        string='Geographical coverage areas')

    x_allowed_product_ids = fields.Many2many(
        'product.product', string='Configured Sub-Services',
        compute='_compute_allowed_product_ids',
        store=False
    )

    x_special_account_ids = fields.Many2many(
        'res.partner',
        'custom_res_partner_special_account_id_rel',
        'partner_id',
        'special_account_id',
        string='Special accounts',
        tracking=True,
    )

    x_exclusive_account_ids = fields.Many2many(
        'res.partner',
        'custom_res_partner_exclusive_account_id_rel',
        'partner_id',
        'exclusive_account_id',
        string='Exclusive_accounts',
        tracking=True,
    )

    x_allowed_account_ids = fields.Many2many(
        'res.partner',
        string='Allowed account',
        compute='_compute_x_allowed_account_ids',
        store=False,
    )

    x_phone_p1 = fields.Char(tracking=True, string='tel_p1')
    x_phone_p1_classification_id = fields.Many2one(
        comodel_name='custom.phone.classification',
        tracking=True)
    x_phone_p2 = fields.Char(tracking=True, string='tel_p2')
    x_phone_p2_classification_id = fields.Many2one(
        comodel_name='custom.phone.classification',
        tracking=True)
    x_phone_p3 = fields.Char(tracking=True, string='tel_p3')
    x_phone_p3_classification_id = fields.Many2one(
        comodel_name='custom.phone.classification',
        tracking=True)
    x_phone_p4 = fields.Char(tracking=True, string='tel_p4')
    x_phone_p4_classification_id = fields.Many2one(
        comodel_name='custom.phone.classification',
        tracking=True)
    x_phone_p5 = fields.Char(tracking=True, string='tel_p5')
    x_phone_p5_classification_id = fields.Many2one(
        comodel_name='custom.phone.classification',
        tracking=True)

    # Relation, driver -> supplier
    x_driver_ids = fields.One2many(
        comodel_name='res.partner.supplier_drivers.rel',
        inverse_name='supplier_id',
        string='Supplier drivers',
    )
    # Relation, driver -> center of attention
    x_ca_driver_ids = fields.One2many(
        comodel_name='res.partner.supplier_drivers.rel',
        inverse_name='center_of_attention_id',
        string='Center of attention drivers',
    )

    # Relation, users -> supplier
    x_users_supplier_ids = fields.One2many(
        comodel_name='res.partner.supplier_users.rel',
        inverse_name='supplier_id',
        string='Supplier users',
    )
    # Relation, users -> center_of_attention
    x_users_ca_ids = fields.One2many(
        comodel_name='res.partner.supplier_users.rel',
        inverse_name='center_of_attention_id',
        string='Center of attention users',
    )
    x_has_portal = fields.Boolean(
        string='Has portal',
        default=False,
        tracking=True
    )

    @api.depends("x_exclusive_account_ids", "x_special_account_ids")
    def _compute_x_allowed_account_ids(self):
        for rec in self:
            accounts_ids = rec.env["res.partner"].search(
                [
                    ('is_company', '=', True),
                    ('x_is_account', '=', True),
                ]
            )
            available_account_ids = set(accounts_ids.ids)
            exclusive_account_ids = set(rec.x_exclusive_account_ids.ids)
            special_account_ids = set(rec.x_special_account_ids.ids)

            allowed_account_ids = (
                available_account_ids - exclusive_account_ids - special_account_ids
            )

            rec.x_allowed_account_ids = [(6, 0, list(allowed_account_ids))]

    def _compute_x_coverage_count(self):
        for rec in self:
            rec.x_coverage_count = rec.env['custom.supplier.coverage.configuration'].search_count([('supplier_id', '=', rec.id)])

    @api.depends('parent_id')
    def _compute_allowed_product_ids(self):
        for rec in self:
            supplier: int = rec.parent_id.id or rec.id
            coverage_id = rec.env['custom.supplier.coverage.configuration'].search([
                ('supplier_id', '=', supplier),
            ], limit=1)

            allowed_product_ids = []
            if coverage_id:
                allowed_product_ids = coverage_id.mapped('supplier_coverage_config_line_ids.product_id.id')

            rec.x_allowed_product_ids = allowed_product_ids

    @api.depends('x_supplier_center_ids', 'x_supplier_center_ids.x_geographical_area_ids')
    def _compute_geographical_area_supplier_ids(self):
        for rec in self:
            rec.x_geographical_area_supplier_ids = (
                rec.x_is_supplier and rec.x_supplier_center_ids.mapped("x_geographical_area_ids").ids or False)

    @api.constrains('name', 'x_is_supplier', 'company_type', 'is_company')
    def _constrains_check_unique_supplier_record(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('x_is_supplier', '=', True),
                ('is_company', '=', True),
                ('id', '<>', rec.id),
            ]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_("A supplier with the same name already exists."))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_("A supplier with the same name already exists. It is disabled."))

    @api.onchange('zip')
    def _onchange_zip(self):
        """ Shows a warning if the zip format is invalid. """
        for partner in self:
            if partner.country_id.code == 'MX' and partner.zip:
                zip_code = partner.zip.strip()

                # Validate that there are exactly 5 numeric digits
                if not zip_code.isdigit() or len(zip_code) != 5:
                    raise ValidationError(_(
                        'The Mexican postal code must contain exactly 5 numeric digits.. '
                        'Example: 03100'
                    ))

                # Validate range (01000 - 99999)
                zip_number = int(zip_code)
                if zip_number < 1000 or zip_number > 99999:
                    raise ValidationError(_(
                        'The postal code must be between 01000 and 99999'
                    ))

    def action_configuration_service_and_subservice_view(self):
        self.ensure_one()
        coverage_ids = self.env['custom.supplier.coverage.configuration'].search([('supplier_id', '=', self.id)])
        action = {
            'name': _('Configuration service and subservice'),
            'view_mode': 'list,form',
            'res_model': 'custom.supplier.coverage.configuration',
            'context': {
                **self.env.context,
                'create': True,
                'default_supplier_id': self.id,
                'search_default_filter_enabled': 1,
            },
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', coverage_ids.ids)],
            'views': [(False, 'list'), (False, 'form')],
        }
        if len(coverage_ids) < 2:
            action['views'] = [(False, 'form')]
            action['res_id'] = coverage_ids.id
        return action

    @api.onchange('x_is_special_accounts')
    def _onchange_x_is_special_accounts(self):
        if not self.x_is_special_accounts and self.x_special_account_ids:
            self.x_special_account_ids = False

    @api.onchange('x_is_exclusive_accounts')
    def _onchange_x_is_exclusive_accounts(self):
        if not self.x_is_exclusive_accounts and self.x_exclusive_account_ids:
            self.x_exclusive_account_ids = False
