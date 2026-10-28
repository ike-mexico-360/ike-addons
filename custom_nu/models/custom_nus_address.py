# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class CustomNusAddress(models.Model):
    _name = 'custom.nus.address'
    _description = 'Custom NUS Address'
    _inherit = ['mail.thread', 'custom.model.encryption']

    _rec_name = 'street_nus'

    nus_id = fields.Many2one('custom.nus', string='NUs', tracking=True, ondelete='cascade')
    active = fields.Boolean(string='Active', default=True, tracking=True)
    disabled = fields.Boolean(string='Disabled', default=False, tracking=True)

    street_nus = fields.Char(string='Street', tracking=True, encrypt=True)
    street2_nus = fields.Char(string='Street2', tracking=True, encrypt=True)
    l10n_mx_edi_colony_nus = fields.Char(string='Colony', tracking=True, encrypt=True)
    city_nus = fields.Char(string='City', tracking=True, encrypt=True)
    state_nus_id = fields.Many2one('res.country.state', string='State', tracking=True, ondelete='restrict')
    zip_nus = fields.Char(string='Zip code', tracking=True, encrypt=True)
    country_nus_id = fields.Many2one('res.country', string='Country', tracking=True, ondelete='restrict')
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_decrypted_fields',
        store=False
    )
    # # === ENCRYPT SEARCH HELPER FIELDS === #
    x_name_search_ids = fields.One2many(
        'custom.nus.address.search.helper.rel', 'encrypt_model_id',
        domain=[('field_name', '=', 'name')])

    # === COMPUTE === #
    @api.depends('street_nus', 'street2_nus', 'l10n_mx_edi_colony_nus', 'city_nus', 'zip_nus')
    def _compute_decrypted_fields(self):
        """
        Compute decrypted values to display in the interface
        """
        for record in self:
            # Decrypt street
            if record.street_nus:
                record.display_name = self.x_decrypt_aes256(record.street_nus)
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


class CustomNusAddressSearchHelperRel(models.Model):
    _name = 'custom.nus.address.search.helper.rel'
    _inherit = ['custom.model.encryption.search.helper.rel']
    _description = 'Custom membership nus search helper rel'

    encrypt_model_id = fields.Many2one('custom.nus.address', ondelete='cascade', index=True, required=True)
    encrypt_helper_id = fields.Many2one('custom.nus.address.search.helper', ondelete='cascade', index=True, required=True)


class CustomNusAddressSearchHelper(models.Model):
    _name = 'custom.nus.address.search.helper'
    _inherit = ['custom.model.encryption.search.helper']
    _description = 'Custom membership nus search helper'

    encrypt_rel_ids = fields.One2many('custom.nus.address.search.helper.rel', 'encrypt_helper_id')
