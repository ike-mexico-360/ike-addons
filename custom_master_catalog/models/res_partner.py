# -*- coding: utf-8 -*-

import re
# from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
# from datetime import datetime


PARTNER_NAME_PATTER = r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s,\.]+$'
SUPPLIER_CENTER_NAME_PATTER = r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s,\.\(\)]+$'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === FIELDS === #
    ref = fields.Char(tracking=True)
    phone = fields.Char(tracking=True)
    mobile = fields.Char(tracking=True)
    email = fields.Char(tracking=True)
    type = fields.Selection(selection_add=[('center', 'Supplier Center')])
    # === FIELDS: NEW === #
    x_is_client = fields.Boolean(string='Client', index=True)
    x_is_supplier = fields.Boolean(string='Supplier', index=True)
    x_is_account = fields.Boolean(string='Account', index=True)
    x_is_ike = fields.Boolean(string="Iké", index=True)
    x_business_name = fields.Char(string='Business Name', tracking=True)
    x_use_parent_invoice_info = fields.Boolean(string='The account is equal to the client', default=False, tracking=True)
    x_partner_contact = fields.Char(string='Partner Contact', tracking=True)
    x_invoice_company_id = fields.Many2one(
        'res.partner',
        'Invoice Company',
        domain=[('x_is_ike', '=', True)],
        tracking=True)
    disabled = fields.Boolean(default=False, index=True, tracking=True)

    # === FIELDS: RELATED PARENT === #
    x_parent_business_name = fields.Char(related='parent_id.x_business_name', string='Parent Business Name')
    x_parent_vat = fields.Char(related='parent_id.vat', string='Parent VAT')
    x_parent_street = fields.Char(related='parent_id.street', string='Parent Street')
    x_parent_street2 = fields.Char(related='parent_id.street2', string='Parent Street2')
    x_parent_colony = fields.Char(related='l10n_mx_edi_colony', string='Parent Colony')
    x_parent_city = fields.Char(related='parent_id.city', string='Parent City')
    x_parent_zip = fields.Char(related='parent_id.zip', string='Parent ZIP')
    x_parent_state_id = fields.Many2one(related='parent_id.state_id', string='Parent State')
    x_parent_country_id = fields.Many2one(related='parent_id.country_id', string='Parent Country')

    # === FIELDS: MX Address === #
    l10n_mx_edi_colony = fields.Char(string="Colony Name", tracking=True)

    # === FIELDS: CLIENT === #
    x_ref_sap = fields.Char(string="SAP Reference", tracking=True)
    x_account_child_ids = fields.One2many(
        'res.partner', 'parent_id',
        domain=[('x_is_account', '=', True)],
        string='Accounts')

    # === FIELDS: SUPPLIER CENTER === #
    x_cost_matrix_ids = fields.One2many(
        'custom.supplier.cost.matrix', 'supplier_center_id',
        string='Cost Matrix')

    # === ONCHANGE === #
    @api.onchange('is_company')
    def _onchange_is_company_type(self):
        if not self.is_company:
            self.x_is_client = False
            self.x_is_supplier = False
            self.x_is_account = False
            self.x_is_ike = False

    @api.onchange('x_use_parent_invoice_info')
    def _onchange_x_use_parent_invoice_info(self):
        if self.x_use_parent_invoice_info:
            # RFC
            self.vat = False
            # Dirección
            self.street = False
            self.street2 = False
            self.l10n_mx_edi_colony = False
            self.city = False
            self.state_id = False
            self.zip = False
            self.country_id = False

    @api.onchange('email')
    def _onchange_email(self):
        """
        Shows a warning if the email format is invalid.
        """
        if self.email:
            # Regular expression for email validation
            regex = r'^[a-zA-Z0-9]+[\._]?[a-zA-Z0-9]+[@]\w+[.]\w{2,3}$'
            if not re.match(regex, self.email):
                self.email = ""
                return {
                    'warning': {
                        'title': _("Formato de Correo Inválido"),
                        'message': _("Por favor, ingresa una dirección de correo electrónico válida."),
                    }
                }

    # === COMPUTE === #
    @api.depends('x_related_partner_ids')
    def _compute_x_related_partner_count(self):
        for rec in self:
            rec.x_related_partner_count = len(rec.x_related_partner_ids)

    # === CONSTRAINS === #
    @api.constrains('name', 'type')
    def _constrains_x_check_name(self):
        for rec in self:
            if rec.type == "center":
                pattern = SUPPLIER_CENTER_NAME_PATTER
                error_message = (_(
                    "El nombre no puede contener caracteres especiales. "
                    "Solo se permiten letras, números, espacios, comas, puntos y paréntesis."
                ))
            else:
                pattern = PARTNER_NAME_PATTER
                error_message = (_(
                    "El nombre no puede contener caracteres especiales. "
                    "El nombre solo puede contener letras, números, espacios, comas y puntos."
                ))
            if not re.match(pattern, rec.name):
                raise ValidationError(error_message)

    @api.constrains('name', 'x_is_client', 'company_type', 'is_company')
    def _constrains_check_unique_client_record(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('x_is_client', '=', True),
                ('company_type', '=', 'company'),
                ('is_company', '=', True),
                ('id', '<>', rec.id),
            ]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_("A client with the same name already exists."))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_("A client with the same name already exists. It is disabled."))

    @api.constrains('vat')
    def _constrains_x_check_vat(self):
        for rec in self.filtered(lambda r: r.vat):
            if rec.x_is_client or rec.x_is_account or rec.x_is_supplier:
                contacts = self.env['res.partner'].search_read([
                    ('vat', '=', rec.vat),
                    ('vat', '!=', False),
                    ('id', '!=', rec.id),
                ], fields=['vat'])
                if contacts and len(contacts) > 0:
                    raise ValidationError(f'Ya existe un registro con RFC ({rec.vat}).')
                if rec.vat and not rec.validate_rfc(rec.vat):
                    raise ValidationError(_(
                        "El RFC debe tener 12(personas moral) o 13(persona física) caracteres, "
                        "3 o 4 letras que forman la clave de la entidad (por ejemplo, "
                        "la primera letra del nombre de la empresa y dos letras adicionales), "
                        "6 dígitos de la fecha de constitución (AA MM DD), "
                        "3 caracteres de homoclave alfanuméricos"
                    ))

    @api.constrains('ref')
    def _constrains_x_check_ref(self):
        for rec in self.filtered(lambda x: x.x_is_client and x.ref):
            contacts = self.env['res.partner'].search_read([
                ('ref', '=', rec.ref),
                ('ref', '!=', False)
            ], fields=['ref'])
            if contacts and len(contacts) > 1:
                raise ValidationError(f'Ya existe un registro con referencia ({rec.ref}).')

    # === CRUD === #
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Client Logic
            if vals.get('x_is_client', False):
                vals['x_business_name'] = vals['name']
        res = super().create(vals_list)
        for rec in res:
            if rec.x_is_supplier and not rec.x_supplier_center_ids:
                rec.create_default_supplier_center()
        return res

    def write(self, vals):
        # Client Logic
        if self.x_is_client and 'name' in vals:
            vals['x_business_name'] = vals['name']

        res = super().write(vals)

        return res

    # === ACTIONS === #
    def action_disable(self, reason=None):
        res = super().action_disable(reason)
        self.notify_disabled(reason)
        return res

    def action_cost_matrix_view(self):
        self.ensure_one()
        action = {
            'name': _('Matriz de costos'),
            'view_mode': 'list,form',
            'res_model': 'custom.supplier.cost.matrix',
            'context': {
                **self.env.context,
                'create': True,
                'default_supplier_center_id': self.id,
                'default_supplier_id': self.parent_id and self.parent_id.id or False,
                'search_default_filter_enabled': 1,
                'from_supplier_center': True
            },
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.x_cost_matrix_ids.ids)],
            'views': [(False, 'list'), (False, 'form')],
        }
        if len(self.x_cost_matrix_ids) < 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = self.x_cost_matrix_ids.id
        return action

    # === PUBLIC METHODS === #
    def get_supplier_center_values(self):
        vals = {
            'parent_id': self.id,
            'name': self.name + str(" (matriz)"),
            'x_parent_vat': self.vat,
            'street': self.street,
            'street2': self.street2,
            'l10n_mx_edi_colony': self.l10n_mx_edi_colony,
            'phone': self.phone,
            'mobile': self.mobile,
            'email': self.email,
            'company_type': 'company',
            'is_company': True,
            'type': 'center'
        }
        return vals

    def create_default_supplier_center(self):
        vals = self.get_supplier_center_values()
        self.env['res.partner'].sudo().create(vals)

    def validate_rfc(self, rfc_str):
        """
        Validates a Mexican RFC for individuals (13 characters) and corporations (12 characters).

        Args:
        rfc_str (str): The text string of the RFC to validate.

        Returns:
        bool: True if the RFC is valid, False otherwise.
        """
        # Check length before regex validation
        if len(rfc_str) == 13:
            # RFC for natural person
            _rfc_pattern_pf = r"^[A-ZÑ&]{4}\d{2}(?:0[13578]|1[02])(?:0[1-9]|[12]\d|3[01])[A-Z0-9]{3}|^[A-ZÑ&]{4}\d{2}(?:0[13456789]|1[012])(?:0[1-9]|[12]\d|30)[A-Z0-9]{3}|^[A-ZÑ&]{4}(?:0[2468][048]|[13579][26])02(?:0[1-9]|1\d|2\d)[A-Z0-9]{3}|^[A-ZÑ&]{4}\d{2}02(?:0[1-9]|1[0-9]|2[0-8])[A-Z0-9]{3}$"
            return re.match(_rfc_pattern_pf, rfc_str) is not None

        elif len(rfc_str) == 12:
            # RFC for legal entity
            _rfc_pattern_pm = r"^[A-ZÑ&]{3}\d{2}(?:0[13578]|1[02])(?:0[1-9]|[12]\d|3[01])[A-Z0-9]{3}|^[A-ZÑ&]{3}\d{2}(?:0[13456789]|1[012])(?:0[1-9]|[12]\d|30)[A-Z0-9]{3}|^[A-ZÑ&]{3}(?:0[2468][048]|[13579][26])02(?:0[1-9]|1\d|2\d)[A-Z0-9]{3}|^[A-ZÑ&]{3}\d{2}02(?:0[1-9]|1[0-9]|2[0-8])[A-Z0-9]{3}$"
            return re.match(_rfc_pattern_pm, rfc_str) is not None
        else:
            return False
