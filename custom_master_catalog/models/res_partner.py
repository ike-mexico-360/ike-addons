# -*- coding: utf-8 -*-

import re
# from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException
# from datetime import datetime


PARTNER_NAME_PATTER = r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s,\.\(\)\-]+$'
SUPPLIER_CENTER_NAME_PATTER = r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s,\.\(\)]+$'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === FIELDS === #
    ref = fields.Char(tracking=True)
    phone = fields.Char(tracking=True)
    mobile = fields.Char(tracking=True)
    email = fields.Char(tracking=True)
    responsible_name = fields.Char(tracking=True)
    type = fields.Selection(selection_add=[('center', 'Supplier Center')])
    country_id = fields.Many2one(default=lambda self: self.env.company.country_id)
    priority = fields.Selection([
        ('0', 'None'),
        ('1', 'Low'),
        ('2', 'Medium'),
        ('3', 'High'),
    ], string='Priority', default='0')
    validation_type = fields.Selection([
        ('data_base', 'Data base'),
        ('portal', 'Portal'),
        ('api', 'API'),
    ], string='Validation type', default='data_base', tracking=True)

    # === FIELDS: NEW === #
    x_is_client = fields.Boolean(string='Client', index=True)
    x_is_supplier = fields.Boolean(string='Supplier', index=True)
    x_is_account = fields.Boolean(string='Account', index=True)
    x_is_ike = fields.Boolean(string="Iké", index=True)
    x_business_name = fields.Char(string='Business Name', tracking=True)
    x_use_parent_invoice_info = fields.Boolean(string='The account is equal to the client', default=False, tracking=True)
    x_partner_contact = fields.Char(string='Partner Contact', tracking=True)
    x_invoice_company_id = fields.Many2many(
        'res.partner',
        'res_partner_invoice_company_rel',
        'partner_id',
        'invoice_company_id',
        'Invoice Company',
        domain=[('x_is_ike', '=', True)],
        tracking=True
    )
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
    x_society_sap = fields.Char(string="SAP Society", tracking=True)
    x_account_child_ids = fields.One2many(
        'res.partner', 'parent_id',
        domain=[('x_is_account', '=', True)],
        string='Accounts')

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
            self.x_business_name = self.parent_id.x_business_name
            # RFC
            self.vat = self.x_parent_vat
            # Dirección
            self.street = self.x_parent_street
            self.street2 = self.x_parent_street2
            self.l10n_mx_edi_colony = self.parent_id.l10n_mx_edi_colony
            self.city = self.x_parent_city
            self.state_id = self.x_parent_state_id and self.x_parent_state_id.id or False
            self.zip = self.x_parent_zip
            self.country_id = self.x_parent_country_id and self.x_parent_country_id.id or False
        else:
            self.x_business_name = False

    # === CONSTRAINS === #
    @api.constrains('name', 'type')
    def _constrains_x_check_name(self):
        for rec in self:
            # if rec.type == "center":
            #     pattern = SUPPLIER_CENTER_NAME_PATTER
            #     error_message = (_(
            #         "El nombre no puede contener caracteres especiales. "
            #         "Solo se permiten letras, números, espacios, comas, puntos y paréntesis."
            #     ))
            # else:
            #     pattern = PARTNER_NAME_PATTER
            #     error_message = (_(
            #         "El nombre no puede contener caracteres especiales. "
            #         "El nombre solo puede contener letras, números, espacios, comas y puntos."
            #     ))
            # allow hyphen and parentheses in all res.partner records
            pattern = PARTNER_NAME_PATTER
            error_message = (_(
                "El nombre no puede contener caracteres especiales. "
                "Solo se permiten letras, números, espacios, comas, puntos, guión medio y paréntesis."
            ))
            if not re.match(pattern, rec.name):
                raise ValidationError(error_message)

    @api.constrains('name', 'x_is_client', 'company_type', 'is_company')
    def _constrains_check_unique_client_record(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('x_is_client', '=', True),
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
            if rec.x_is_client or rec.x_is_supplier or rec.x_is_ike:
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
        for record in self:
            if record.x_is_client and 'name' in vals:
                vals['x_business_name'] = vals['name']
        res = super().write(vals)

        if 'priority' in vals:
            area = self.env['custom.geographical.area']
            for partner in self:
                child_records = area.search([('parent_id', '=', partner.id)])
                if child_records:
                    child_records.write({'priority': partner.priority})
        return res

    # === ACTIONS === #
    def action_disable(self, reason=None):
        res = super().action_disable(reason)
        for record in self:
            record.notify_disabled(reason)
        return res

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

    @api.onchange('phone', 'country_id', 'company_id')
    def _onchange_phone_validation(self):
        return self._phone_number_validation('phone')

    @api.onchange('mobile', 'country_id', 'company_id')
    def _onchange_mobile_validation(self):
        return self._phone_number_validation('mobile')

    @api.onchange('x_phone_p1', 'country_id', 'company_id')
    def _onchange_x_phone_p1_validation(self):
        return self._phone_number_validation('x_phone_p1')

    @api.onchange('x_phone_p2', 'country_id', 'company_id')
    def _onchange_x_phone_p2_validation(self):
        return self._phone_number_validation('x_phone_p2')

    @api.onchange('x_phone_p3', 'country_id', 'company_id')
    def _onchange_x_phone_p3_validation(self):
        return self._phone_number_validation('x_phone_p3')

    @api.onchange('x_phone_p4', 'country_id', 'company_id')
    def _onchange_x_phone_p4_validation(self):
        return self._phone_number_validation('x_phone_p4')

    @api.onchange('x_phone_p5', 'country_id', 'company_id')
    def _onchange_x_phone_p5_validation(self):
        return self._phone_number_validation('x_phone_p5')

    def _phone_number_validation(self, phone_number_field='phone'):
        """
        Validates a phone number in any field

        Args:
            phone_number_field (str): Name of the field to validate (default 'phone')

        Returns:
            dict or False: Dictionary with warning if invalid, False if valid
        """
        phone_number = getattr(self, phone_number_field, False)

        if not phone_number:
            return False

        # Get country for validation
        country_id = self.country_id
        if not country_id:
            country_id = list(self._phone_get_country())[0] if self._phone_get_country() else False
        if not country_id:
            country_id = self.env.company.country_id

        # First, obtain the country code from the phone number
        phone_code = None
        try:
            # Parse the number to extract the country code
            parsed_number = phonenumbers.parse(phone_number, None)
            if parsed_number and parsed_number.country_code:
                phone_code = str(parsed_number.country_code)
        except:
            pass

        # Compare with the contact's country code
        if country_id and phone_code:
            # Convert the model's country code to a string
            country_code = country_id.code
            if country_code:
                # Compare the codes (formatting may need to be adjusted)

                if country_id.phone_code and str(phone_code) != str(country_id.phone_code):
                    raise ValidationError(_("The country code in the phone number (+%s) does not match the country (%s).",
                                    phone_code, country_id.name))

        # Format phone number to international format
        formatted_phone = self._phone_format(fname=phone_number_field, force_format='INTERNATIONAL')

        # Verify if the international format is valid
        if not formatted_phone:
            country_name = country_id.name if country_id else _("unknown")
            raise ValidationError(_("The entered phone number is not valid for country %s", country_name))

        # Update field with international format
        setattr(self, phone_number_field, formatted_phone or "")

        return False
