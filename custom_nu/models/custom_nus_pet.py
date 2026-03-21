# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class CustomNusPet(models.Model):
    _name = 'custom.nus.pet'
    _description = 'Custom NUS Pet'
    _inherit = ['mail.thread']

    # === FIELDS === #
    name = fields.Char(string="Name", required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    disabled = fields.Boolean(string='Disabled', default=False, tracking=True)
    pet_type_id = fields.Many2one('custom.nus.pet.type', string='Type', required=True, tracking=True)
    breed_id = fields.Many2one(
        'custom.nus.pet.breed',
        string='Breed', domain="[('pet_type_id', '=', pet_type_id)]",
        tracking=True
    )
    birthdate = fields.Date(string="Birthdate", tracking=True)
    nus_id = fields.Many2one('custom.nus', string='NUs', tracking=True)
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_decrypted_fields',
        store=False
    )

    # === ONCHANGE === #
    @api.onchange('pet_type_id')
    def _onchange_pet_type(self):
        for record in self:
            if record.breed_id and record.pet_type_id:
                if record.breed_id.pet_type_id != record.pet_type_id:
                    record.breed_id = False

    # === COMPUTE === #
    @api.depends('name')
    def _compute_decrypted_fields(self):
        """
        Compute decrypted values to display in the interface
        """
        encryption_util = self.env['custom.encryption.utility']
        for record in self:
            # Decrypt name
            if record.name:
                record.display_name = encryption_util.decrypt_aes256(record.name)
            else:
                record.display_name = ''

    # === CRUD METHODS === #
    @api.model_create_multi
    def create(self, vals_list):
        encryption_util = self.env['custom.encryption.utility']

        for vals in vals_list:

            if 'name' in vals and vals['name']:
                vals['name'] = encryption_util.encrypt_aes256(vals['name'])

        return super(CustomNusPet, self).create(vals_list)

    def write(self, vals):
        if not vals:
            return True

        encryption_util = self.env['custom.encryption.utility']

        # Encriptar campos
        if 'name' in vals and vals['name']:
            vals['name'] = encryption_util.encrypt_aes256(vals['name'])

        return super(CustomNusPet, self).write(vals)

    def read(self, fields=None, load='_classic_read'):
        """
        Override read to return decrypted values when necessary
        """
        result = super(CustomNusPet, self).read(fields=fields, load=load)

        # Only decrypt if encrypted fields are specifically requested
        if not fields or any(f in fields for f in ['name']):
            encryption_util = self.env['custom.encryption.utility']

            for record in result:
                if 'name' in record and record['name']:
                    try:
                        record['name'] = encryption_util.decrypt_aes256(record['name'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting name: {str(e)}")

        return result

    def name_get(self):
        """
        Override name_get to display the decrypted name
        This is what makes the _rec_name appear decrypted throughout the application
        """
        result = []
        encryption_util = self.env['custom.encryption.utility']
        for record in self:
            if record.name:
                decrypted_name = encryption_util.decrypt_aes256(record.name)
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
            return super(CustomNusPet, self).name_search(name, args, operator, limit)

        # Search in all records and filter by decrypted name
        records = self.search(args or [])
        encryption_util = self.env['custom.encryption.utility']
        matching_ids = []

        for record in records:
            if record.name:
                try:
                    decrypted_name = encryption_util.decrypt_aes256(record.name)
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
