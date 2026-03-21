# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CustomNusAddress(models.Model):
    _name = 'custom.nus.address'
    _description = 'Custom NUS Address'
    _inherit = ['mail.thread']

    _rec_name = 'street_nus'

    nus_id = fields.Many2one('custom.nus', string='NUs', tracking=True, ondelete='cascade')
    active = fields.Boolean(string='Active', default=True, tracking=True)
    disabled = fields.Boolean(string='Disabled', default=False, tracking=True)

    street_nus = fields.Char(string='Street', tracking=True)
    street2_nus = fields.Char(string='Street2', tracking=True)
    l10n_mx_edi_colony_nus = fields.Char(string='Colony', tracking=True)
    city_nus = fields.Char(string='City', tracking=True)
    state_nus_id = fields.Many2one('res.country.state', string='State', tracking=True, ondelete='restrict')
    zip_nus = fields.Char(string='Zip code', tracking=True)
    country_nus_id = fields.Many2one('res.country', string='Country', tracking=True, ondelete='restrict')
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_decrypted_fields',
        store=False
    )

    # === COMPUTE === #
    @api.depends('street_nus', 'street2_nus', 'l10n_mx_edi_colony_nus', 'city_nus', 'zip_nus')
    def _compute_decrypted_fields(self):
        """
        Compute decrypted values to display in the interface
        """
        encryption_util = self.env['custom.encryption.utility']
        for record in self:
            # Decrypt street
            if record.street_nus:
                record.display_name = encryption_util.decrypt_aes256(record.street_nus)
            else:
                record.display_name = ''

    # === ONCHANGE === #
    @api.onchange('zip_nus')
    def _onchange_zip(self):
        """ Shows a warning if the zip format is invalid. """
        for partner in self:
            if partner.country_nus_id.code == 'MX' and partner.zip_nus:
                zip_code = partner.zip_nus.strip()

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

    @api.onchange('state_nus_id')
    def _onchange_state_id(self):
        for rec in self:
            if rec.state_nus_id:
                rec.country_nus_id = rec.state_nus_id.country_id

    @api.onchange('country_nus_id')
    def _onchange_country_id(self):
        for rec in self:
            if rec.country_nus_id and rec.state_nus_id and rec.state_nus_id.country_id != rec.country_nus_id:
                rec.state_nus_id = False

    # === CRUD METHODS === #
    @api.model_create_multi
    def create(self, vals_list):
        encryption_util = self.env['custom.encryption.utility']

        for vals in vals_list:

            # Encriptar campos
            if 'street_nus' in vals and vals['street_nus']:
                vals['street_nus'] = encryption_util.encrypt_aes256(vals['street_nus'])
            if 'street2_nus' in vals and vals['street2_nus']:
                vals['street2_nus'] = encryption_util.encrypt_aes256(vals['street2_nus'])
            if 'l10n_mx_edi_colony_nus' in vals and vals['l10n_mx_edi_colony_nus']:
                vals['l10n_mx_edi_colony_nus'] = encryption_util.encrypt_aes256(vals['l10n_mx_edi_colony_nus'])
            if 'city_nus' in vals and vals['city_nus']:
                vals['city_nus'] = encryption_util.encrypt_aes256(vals['city_nus'])
            if 'zip_nus' in vals and vals['zip_nus']:
                vals['zip_nus'] = encryption_util.encrypt_aes256(vals['zip_nus'])

        return super(CustomNusAddress, self).create(vals_list)

    def write(self, vals):
        if not vals:
            return True

        encryption_util = self.env['custom.encryption.utility']

        # Encrypt fields
        if 'street_nus' in vals and vals['street_nus']:
            vals['street_nus'] = encryption_util.encrypt_aes256(vals['street_nus'])
        if 'street2_nus' in vals and vals['street2_nus']:
            vals['street2_nus'] = encryption_util.encrypt_aes256(vals['street2_nus'])
        if 'l10n_mx_edi_colony_nus' in vals and vals['l10n_mx_edi_colony_nus']:
            vals['l10n_mx_edi_colony_nus'] = encryption_util.encrypt_aes256(vals['l10n_mx_edi_colony_nus'])
        if 'city_nus' in vals and vals['city_nus']:
            vals['city_nus'] = encryption_util.encrypt_aes256(vals['city_nus'])
        if 'zip_nus' in vals and vals['zip_nus']:
            vals['zip_nus'] = encryption_util.encrypt_aes256(vals['zip_nus'])

        return super(CustomNusAddress, self).write(vals)

    def read(self, fields=None, load='_classic_read'):
        """
        Override read to return decrypted values when necessary
        """
        result = super(CustomNusAddress, self).read(fields=fields, load=load)

        # Only decrypt if encrypted fields are specifically requested
        if not fields or any(f in fields for f in ['street_nus', 'street2_nus', 'l10n_mx_edi_colony_nus', 'city_nus', 'zip_nus']):
            encryption_util = self.env['custom.encryption.utility']

            for record in result:
                if 'street_nus' in record and record['street_nus']:
                    try:
                        record['street_nus'] = encryption_util.decrypt_aes256(record['street_nus'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting Street: {str(e)}")

                if 'street2_nus' in record and record['street2_nus']:
                    try:
                        record['street2_nus'] = encryption_util.decrypt_aes256(record['street2_nus'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting Street2: {str(e)}")

                if 'l10n_mx_edi_colony_nus' in record and record['l10n_mx_edi_colony_nus']:
                    try:
                        record['l10n_mx_edi_colony_nus'] = encryption_util.decrypt_aes256(record['l10n_mx_edi_colony_nus'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting Colony: {str(e)}")

                if 'city_nus' in record and record['city_nus']:
                    try:
                        record['city_nus'] = encryption_util.decrypt_aes256(record['city_nus'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting City: {str(e)}")
                if 'zip_nus' in record and record['zip_nus']:
                    try:
                        record['zip_nus'] = encryption_util.decrypt_aes256(record['zip_nus'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting Zip code: {str(e)}")

        return result

    def name_get(self):
        """
        Override name_get to display the decrypted name
        This is what makes the _rec_name appear decrypted throughout the application
        """
        result = []
        encryption_util = self.env['custom.encryption.utility']
        for record in self:
            if record.street_nus:
                decrypted_name = encryption_util.decrypt_aes256(record.street_nus)
                result.append((record.id, decrypted_name))
            else:
                result.append((record.id, 'No name'))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """
        Override name_search to search in decrypted names
        This allows searching records by their decrypted name
        """
        if not name:
            return super(CustomNusAddress, self).name_search(name, args, operator, limit)

        # Search in all records and filter by decrypted name
        records = self.search(args or [])
        encryption_util = self.env['custom.encryption.utility']
        matching_ids = []

        for record in records:
            if record.street_nus:
                try:
                    decrypted_name = encryption_util.decrypt_aes256(record.street_nus)
                    if operator == 'ilike' and name.lower() in decrypted_name.lower():
                        matching_ids.append(record.id)
                    elif operator == '=' and name == decrypted_name:
                        matching_ids.append(record.id)
                    elif operator == 'like' and name in decrypted_name:
                        matching_ids.append(record.id)
                except Exception as e:
                    _logger.warning(f"Error decrypting name for search: {str(e)}")
                    continue

            if len(matching_ids) >= limit:
                break

        return self.browse(matching_ids).name_get()
