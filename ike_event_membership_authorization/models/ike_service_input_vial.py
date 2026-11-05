# -*- coding: utf-8 -*-
from odoo import models, api


class IkeServiceInputVial(models.Model):
    _inherit = 'ike.service.input.vial'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records.filtered(lambda x: not x.vehicle_plate):
            plate = rec._get_membership_plate()
            if plate:
                rec.vehicle_plate = plate
        return records

    def _get_membership_plate(self):
        """Return the decrypted membership key whose account identification is a plate
        (primary first, then second key), captured in the register user wizard."""
        self.ensure_one()
        membership_id = self.event_id.user_membership_id
        account_id = membership_id.membership_plan_id.account_id
        if not account_id:
            return False
        if account_id.x_account_identification_id.is_plate and membership_id.key_identification:
            encrypted_plate = membership_id.key_identification
        elif (
            account_id.x_check_second_key
            and account_id.x_second_key_identification_id.is_plate
            and membership_id.second_key_identification
        ):
            encrypted_plate = membership_id.second_key_identification
        else:
            return False
        return self.env['custom.model.encryption'].x_decrypt_aes256(encrypted_plate) or False
