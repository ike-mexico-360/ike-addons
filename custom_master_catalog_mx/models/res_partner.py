import re
from odoo import models, api, _
from odoo.exceptions import ValidationError

PARTNER_NAME_PATTER = r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s,\.\(\)\-&\/]+$'
SUPPLIER_CENTER_NAME_PATTER = r'^[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ\s,\.\(\)]+$'


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def validate_rfc(self, rfc_str):
        """ Validates a Mexican RFC for individuals (13 characters) and corporations (12 characters). """
        if not rfc_str:
            return False
        if len(rfc_str) == 13:
            _rfc_pattern_pf = r"^[A-ZÑ&]{4}\d{2}(?:0[13578]|1[02])(?:0[1-9]|[12]\d|3[01])[A-Z0-9]{3}|^[A-ZÑ&]{4}\d{2}(?:0[13456789]|1[012])(?:0[1-9]|[12]\d|30)[A-Z0-9]{3}|^[A-ZÑ&]{4}(?:0[2468][048]|[13579][26])02(?:0[1-9]|1\d|2\d)[A-Z0-9]{3}|^[A-ZÑ&]{4}\d{2}02(?:0[1-9]|1[0-9]|2[0-8])[A-Z0-9]{3}$"
            return re.match(_rfc_pattern_pf, rfc_str) is not None
        elif len(rfc_str) == 12:
            _rfc_pattern_pm = r"^[A-ZÑ&]{3}\d{2}(?:0[13578]|1[02])(?:0[1-9]|[12]\d|3[01])[A-Z0-9]{3}|^[A-ZÑ&]{3}\d{2}(?:0[13456789]|1[012])(?:0[1-9]|[12]\d|30)[A-Z0-9]{3}|^[A-ZÑ&]{3}(?:0[2468][048]|[13579][26])02(?:0[1-9]|1\d|2\d)[A-Z0-9]{3}|^[A-ZÑ&]{3}\d{2}02(?:0[1-9]|1[0-9]|2[0-8])[A-Z0-9]{3}$"
            return re.match(_rfc_pattern_pm, rfc_str) is not None
        return False

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
            if not re.match(PARTNER_NAME_PATTER, rec.name):
                raise ValidationError(_(
                    "The name cannot contain special characters. "
                    "Only letters, numbers, spaces, commas, periods, hyphens, slashes, parentheses, and the '&' symbol are allowed."
                ))

    def _validate_vat_number(self, vat_number):
        """ Validates a Mexican VAT number. """
        if not vat_number:
            return False

        return self.validate_rfc(vat_number)
