# -*- coding: utf-8 -*-
from odoo import models, fields, _

import logging
_logger = logging.getLogger(__name__)


class IkeEvent(models.Model):
    _inherit = 'ike.event'

    membership_authorization_id = fields.Many2one('ike.event.membership.authorization', copy=False)
    event_coverage_authorizer = fields.Boolean()
    required_commercial_authorizer = fields.Boolean()

    membership_authorization_status = fields.Selection(
        related="membership_authorization_id.state",
        store=False
    )
    check_commercial_authorization = fields.Boolean(
        related='membership_authorization_id.check_commercial_authorization',
        string='Required commercial authorization'
    )
    # ike_event_api
    created_from_bp = fields.Boolean(
        string="Created from BP", copy=False,
        help="Technical (BP): Flag to indicate that the current event was created from a call from the BrightPattern service")
    temporary_phone = fields.Char(
        string="Temporary phone", copy=False,
        help="Technical (BP): This field will temporarily store the value received from BrightPattern when there is no record matching the phone number.")
    temporary_key_identification = fields.Char(
        string="Temporary key identification", copy=False,
        help="Technical (BP): Field that temporarily stores the value received from Bright Pattern when there is no record matching the identification key.")
    temporary_membership_plan_id = fields.Many2one(
        'custom.membership.plan', string="Temporary account", copy=False,
        help="Technical (BP): Field that temporarily stores the coverage plan value corresponding to the BrightPattern call")

    # ACTIONS
    def action_view_authorization(self):
        self.ensure_one()
        return self.membership_authorization_id.with_context(self.env.context).action_authororizer_wizard()

    def action_update_nu_name(self):
        result = super().action_update_nu_name()  # type: ignore

        # ToDo - refactor to self.user_id when testing is no longer being done
        if not result and self.user_membership_id.membership_plan_id.account_id.validation_type == 'portal':  # type: ignore
            return self.action_open_register_user_wizard()
        return result

    def action_open_register_user_wizard(self):
        self.ensure_one()
        # phone = super()._get_phone(self.user_phone)  # type: ignore
        decrypt_encrypt_utility_sudo = self.env['custom.encryption.utility']
        ctx = {
            'default_account_id': self.user_membership_id.membership_plan_id.id,
            'default_event_id': self.id,
            'default_phone': decrypt_encrypt_utility_sudo.decrypt_aes256(self.user_phone)
        }
        # Implementando flujo de BP, cuenta no existente
        if bool(self.created_from_bp and self.temporary_phone):
            ctx.update({
                'created_from_bp': self.created_from_bp,
                'default_account_id': self.temporary_membership_plan_id.id,
                'default_key_primary': self.temporary_key_identification,
                'default_phone': self.temporary_phone,
            })
        else:
            if self.user_id and self.user_membership_id:
                membership_ids = self.env['custom.membership.nus'].search([
                    ('nus_id', '=', self.user_id.id),
                    ('membership_plan_id', '=', self.user_membership_id.membership_plan_id.id),
                ])
                if len(membership_ids) == 1:
                    key_primary = decrypt_encrypt_utility_sudo.decrypt_aes256(membership_ids[0].key_identification)
                    ctx.update({
                        'default_key_primary': key_primary,
                    })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Registro de usuario',
            'res_model': 'ike.add.affiliation.nu.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx
        }
