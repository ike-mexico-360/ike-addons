# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class CustomMembershipNus(models.Model):
    _name = 'custom.membership.nus'
    _description = 'Custom Membership NUs'
    _inherit = ['mail.thread']

    # Use name for rec_name (it will be automatically decrypted in name_get)
    _rec_name = 'name'

    name = fields.Char(string='Name', default=lambda self: _("New"), required=True, tracking=True)
    key_identification = fields.Char(
        string="Key identification",
        tracking=True)
    second_key_identification = fields.Char(
        string="Second key identification",
        tracking=True)
    clause = fields.Char()
    second_clause = fields.Char(string="second clause")
    date = fields.Date(string='Date', tracking=True, default=fields.Date.context_today)
    x_validation_pattern = fields.Char(string='Validation pattern', related="membership_plan_id.x_validation_pattern")
    x_display_mask = fields.Char(string='Display mask', related="membership_plan_id.x_display_mask")
    x_validation_pattern_second = fields.Char(
        string='Validation second pattern',
        related="membership_plan_id.x_validation_pattern_second")
    x_display_mask_second = fields.Char(string='Second display mask', related="membership_plan_id.x_display_mask_second")
    check_second_key = fields.Boolean(related="membership_plan_id.account_id.x_check_second_key")
    check_clause = fields.Boolean(related="membership_plan_id.account_identification_id.clause", string="Check clause")
    second_check_clause = fields.Boolean(related="membership_plan_id.second_account_identification_id.clause", string="Second check clause")

    nus_id = fields.Many2one(
        comodel_name='custom.nus',
        string='NUs',
        tracking=True)
    membership_plan_id = fields.Many2one(
        comodel_name='custom.membership.plan',
        string='Membership plan',
        tracking=True)
    vehicle_weight_category_id = fields.Many2one(
        'custom.vehicle.weight.category',
        string='Weight Category',
        tracking=True
    )
    check_is_fleet = fields.Boolean()
    check_is_special = fields.Boolean()
    display_key_primary_clause = fields.Char()
    display_key_second_clause_second = fields.Char()

    active = fields.Boolean(string='Active', default=True)
    disabled = fields.Boolean(string='Disabled', default=False, tracking=True)
    subscription_validity = fields.Boolean()
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_decrypted_fields',
        store=False
    )
    date_start = fields.Date(string='Start date', store=True)
    date_end = fields.Date(string='Date End', store=True)

    # === COMPUTE === #
    @api.depends('name', 'key_identification', 'x_validation_pattern', 'x_display_mask')
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

    # === ONVHANGE === #
    @api.onchange('membership_plan_id')
    def onchange_membership_plan_dates(self):
        """
        Updates start and end dates automatically whenever the membership plan changes.
        """
        if self.membership_plan_id:
            # We assign values directly to ensure they refresh on every plan change
            self.date_start = self.membership_plan_id.contract_start_date
            self.date_end = self.membership_plan_id.contract_end_date
        else:
            # Optional: Clear dates if the plan is removed
            self.date_start = False
            self.date_end = False

    # === CRUD METHODS === #
    @api.model_create_multi
    def create(self, vals_list):
        encryption_util = self.env['custom.encryption.utility']

        for vals in vals_list:
            # Asignar secuencia si name es "New" o no viene definido
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("custom.membership.nus") or _("New")

            # Encriptar campos
            if 'name' in vals and vals['name']:
                vals['name'] = encryption_util.encrypt_aes256(vals['name'])
            if 'key_identification' in vals and vals['key_identification']:
                vals['key_identification'] = encryption_util.encrypt_aes256(vals['key_identification'])
            if 'x_validation_pattern' in vals and vals['x_validation_pattern']:
                vals['x_validation_pattern'] = encryption_util.encrypt_aes256(vals['x_validation_pattern'])
            if 'x_display_mask' in vals and vals['x_display_mask']:
                vals['x_display_mask'] = encryption_util.encrypt_aes256(vals['x_display_mask'])

        return super(CustomMembershipNus, self).create(vals_list)

    def write(self, vals):
        if not vals:
            return True

        encryption_util = self.env['custom.encryption.utility']

        # Encrypt fields
        if 'name' in vals and vals['name']:
            vals['name'] = encryption_util.encrypt_aes256(vals['name'])
        if 'key_identification' in vals and vals['key_identification']:
            vals['key_identification'] = encryption_util.encrypt_aes256(vals['key_identification'])
        if 'x_validation_pattern' in vals and vals['x_validation_pattern']:
            vals['x_validation_pattern'] = encryption_util.encrypt_aes256(vals['x_validation_pattern'])
        if 'x_display_mask' in vals and vals['x_display_mask']:
            vals['x_display_mask'] = encryption_util.encrypt_aes256(vals['x_display_mask'])

        return super(CustomMembershipNus, self).write(vals)

    def read(self, fields=None, load='_classic_read'):
        """
        Override read to return decrypted values when necessary
        """
        result = super(CustomMembershipNus, self).read(fields=fields, load=load)

        # Only decrypt if encrypted fields are specifically requested
        if not fields or any(f in fields for f in ['name', 'key_identification', 'x_validation_pattern', 'x_display_mask']):
            encryption_util = self.env['custom.encryption.utility']

            for record in result:
                if 'name' in record and record['name']:
                    try:
                        record['name'] = encryption_util.decrypt_aes256(record['name'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting name: {str(e)}")

                if 'key_identification' in record and record['key_identification']:
                    try:
                        record['key_identification'] = encryption_util.decrypt_aes256(record['key_identification'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting Key identification: {str(e)}")

                if 'x_validation_pattern' in record and record['x_validation_pattern']:
                    try:
                        record['x_validation_pattern'] = encryption_util.decrypt_aes256(record['x_validation_pattern'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting Validation pattern: {str(e)}")

                if 'x_display_mask' in record and record['x_display_mask']:
                    try:
                        record['x_display_mask'] = encryption_util.decrypt_aes256(record['x_display_mask'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting Display mask: {str(e)}")

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
            return super(CustomMembershipNus, self).name_search(name, args, operator, limit)

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

    # === ACTIONS === #
    def action_disable(self, reason=None):
        for rec in self:
            if reason:
                body = Markup("""
                    <ul class="mb-0 ps-4">
                        <li>
                            <b>{}: </b><span class="">{}</span>
                        </li>
                    </ul>
                """).format(
                    _('Disabled'),
                    reason,
                )
                rec.message_post(
                    body=body,
                    message_type='notification',
                    body_is_html=True)
        return super().action_disable(reason)
