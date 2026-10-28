# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class CustomNusPet(models.Model):
    _name = 'custom.nus.pet'
    _description = 'Custom NUS Pet'
    _inherit = ['mail.thread', 'custom.model.encryption']

    # === FIELDS === #
    name = fields.Char(string="Name", required=True, tracking=True, encrypt=True)
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
    # # === ENCRYPT SEARCH HELPER FIELDS === #
    x_name_search_ids = fields.One2many(
        'custom.nus.pet.search.helper.rel', 'encrypt_model_id',
        domain=[('field_name', '=', 'name')])

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
        for record in self:
            # Decrypt name
            if record.name:
                record.display_name = self.x_decrypt_aes256(record.name)
            else:
                record.display_name = ''


class CustomNusPetSearchHelperRel(models.Model):
    _name = 'custom.nus.pet.search.helper.rel'
    _inherit = ['custom.model.encryption.search.helper.rel']
    _description = 'Custom membership nus search helper rel'

    encrypt_model_id = fields.Many2one('custom.nus.pet', ondelete='cascade', index=True, required=True)
    encrypt_helper_id = fields.Many2one('custom.nus.pet.search.helper', ondelete='cascade', index=True, required=True)


class CustomNusPetsearchHelper(models.Model):
    _name = 'custom.nus.pet.search.helper'
    _inherit = ['custom.model.encryption.search.helper']
    _description = 'Custom membership nus search helper'

    encrypt_rel_ids = fields.One2many('custom.nus.address.search.helper.rel', 'encrypt_helper_id')
