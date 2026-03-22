# -*- coding: utf-8 -*-

import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CustomNusVehicle(models.Model):
    _name = 'custom.nus.vehicle'
    _description = 'Custom NUS Vehicle'
    _inherit = ['mail.thread']

    _rec_name = 'model_nus_id'

    # === FIELDS === #
    nus_id = fields.Many2one('custom.nus', string='NUs', tracking=True)
    vehicle_year = fields.Char(string='Year', tracking=True)
    model_nus_id = fields.Many2one('fleet.vehicle.model', string='Model', tracking=True)
    vehicle_category_id = fields.Many2one(
        'fleet.vehicle.model.category',
        'Category',
        domain="[('disabled', '=', False)]",
        tracking=True)
    license_plate_nus = fields.Char(string='License Plate', tracking=True)
    vin_sn_nus = fields.Char(string='Chassis Number', tracking=True)
    image_128 = fields.Binary(
        string='Image 128',
        related='model_nus_id.image_128',
        store=False,
        readonly=True
    )

    # === CONSTRAINT METHODS === #
    @api.constrains('vin_sn_nus')
    def _validate_vin_sn_nus_format_and_unique(self):
        vin_regex = r'^[A-HJ-NPR-Z0-9]{17}$'
        encryption_util = self.env['custom.encryption.utility']

        for record in self:
            vin_encrypted = record.vin_sn_nus
            if vin_encrypted:
                try:
                    vin = encryption_util.decrypt_aes256(vin_encrypted).upper()
                except Exception:
                    raise ValidationError(_("The chassis number (VIN) could not be validated."))

                if len(vin) != 17:
                    raise ValidationError(_(
                        "- The VIN must be exactly 17 characters long (currently %(length)d)."
                    ) % {'length': len(vin)})

                if not re.match(vin_regex, vin):
                    raise ValidationError(_(
                        "- The VIN contains invalid characters. Letters I, O, and Q are not allowed."
                    ))

                # existing = self.search([
                #     ('vin_sn_nus', '=', vin),
                #     ('id', '!=', record.id)
                # ])
                # if existing:
                #     raise ValidationError(_("The chassis number (VIN) must be unique!"))

    # === CRUD METHODS === #
    @api.model_create_multi
    def create(self, vals_list):
        encryption_util = self.env['custom.encryption.utility']

        for vals in vals_list:
            # Convertir VIN y placa a mayúsculas
            if 'vin_sn_nus' in vals and vals['vin_sn_nus']:
                vals['vin_sn_nus'] = vals['vin_sn_nus'].upper()
            if 'license_plate_nus' in vals and vals['license_plate_nus']:
                vals['license_plate_nus'] = vals['license_plate_nus'].upper()

            # Encriptar campos
            if 'license_plate_nus' in vals and vals['license_plate_nus']:
                vals['license_plate_nus'] = encryption_util.encrypt_aes256(vals['license_plate_nus'])
            if 'vin_sn_nus' in vals and vals['vin_sn_nus']:
                vals['vin_sn_nus'] = encryption_util.encrypt_aes256(vals['vin_sn_nus'])
            if 'vehicle_year' in vals and vals['vehicle_year']:
                year = vals['vehicle_year']
                if not year.isdigit():
                    raise ValidationError(_("Year must contain only numbers."))
                if len(year) != 4:
                    raise ValidationError(_("Year must be 4 digits."))
                vals['vehicle_year'] = encryption_util.encrypt_aes256(year)

        return super(CustomNusVehicle, self).create(vals_list)

    def write(self, vals):
        if not vals:
            return True

        encryption_util = self.env['custom.encryption.utility']

        # Convertir campos a mayúsculas antes de encriptar
        if 'vin_sn_nus' in vals and vals['vin_sn_nus']:
            vals['vin_sn_nus'] = vals['vin_sn_nus'].upper()

        # Encriptar campos
        if 'vin_sn_nus' in vals and vals['vin_sn_nus']:
            vals['vin_sn_nus'] = encryption_util.encrypt_aes256(vals['vin_sn_nus'])
        if 'license_plate_nus' in vals and vals['license_plate_nus']:
            vals['license_plate_nus'] = encryption_util.encrypt_aes256(vals['license_plate_nus'])
        if 'vehicle_year' in vals and vals['vehicle_year']:
            year = vals['vehicle_year']
            if not year.isdigit():
                raise ValidationError(_("Year must contain only numbers."))
            if len(year) != 4:
                raise ValidationError(_("Year must be 4 digits."))
            vals['vehicle_year'] = encryption_util.encrypt_aes256(year)

        return super(CustomNusVehicle, self).write(vals)

    def read(self, fields=None, load='_classic_read'):
        """
        Override read to return decrypted values when necessary
        """
        result = super(CustomNusVehicle, self).read(fields=fields, load=load)

        # Only decrypt if encrypted fields are specifically requested
        if not fields or any(f in fields for f in ['vin_sn_nus', 'license_plate_nus']):
            encryption_util = self.env['custom.encryption.utility']

            for record in result:
                if 'vin_sn_nus' in record and record['vin_sn_nus']:
                    try:
                        record['vin_sn_nus'] = encryption_util.decrypt_aes256(record['vin_sn_nus'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting vin_sn_nus: {str(e)}")

                if 'license_plate_nus' in record and record['license_plate_nus']:
                    try:
                        record['license_plate_nus'] = encryption_util.decrypt_aes256(record['license_plate_nus'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting license_plate_nus: {str(e)}")
                if 'vehicle_year' in record and record['vehicle_year']:
                    try:
                        record['vehicle_year'] = encryption_util.decrypt_aes256(record['vehicle_year'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting vehicle_year: {str(e)}")

        return result

    def check_encrypted_field(self, field_name, value_to_check):
        """
        Check if a value matches an encrypted field

        Args:
            field_name (str): Name of the encrypted field to verify
            value_to_check (str): Value to compare with the decrypted field

        Returns:
            bool: True if value matches, False otherwise or if there's an error
        """
        if value_to_check:
            encryption_util = self.env['custom.encryption.utility']
            value_to_check = value_to_check.upper()

            # Verify the field exists in the model
            if field_name not in self._fields:
                _logger.warning(f"Field '{field_name}' does not exist in model {self._name}")
                return False

            try:
                # Get encrypted value from the specified field
                encrypted_value = getattr(self, field_name)

                # If field is empty, return False
                if not encrypted_value:
                    return False

                # Decrypt the value
                decrypted_value = encryption_util.decrypt_aes256(encrypted_value)

                # Compare values (uppercase for case-insensitive comparison)
                if decrypted_value.upper() == value_to_check:
                    return True

            except Exception as e:
                _logger.warning(f"Error decrypting field '{field_name}' for record {self.id}: {str(e)}")
                return False

        return False
