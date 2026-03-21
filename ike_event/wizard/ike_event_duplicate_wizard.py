# -*- coding: utf-8 -*-

from odoo import models, fields, api


class IkeEventDuplicateWizard(models.TransientModel):
    _name = "ike.event.duplicate.wizard"
    _description = "Duplicate event wizard"

    # EVENT ID
    event_id = fields.Many2one('ike.event')
    duplicate_reason_id = fields.Many2one('ike.event.duplicate.reason', domain="[('disabled', '=', False)]")

    # NU FIELDS
    nu_name = fields.Char('Nu user name')
    vip_user = fields.Boolean(related='event_id.vip_user')
    user_membership_id = fields.Many2one(related='event_id.user_membership_id')
    user_phone = fields.Char(related='event_id.user_phone')
    membership_display_mask = fields.Char(related='event_id.membership_display_mask')
    key_identification = fields.Char(related="event_id.user_membership_id.key_identification")
    second_key_identification = fields.Char(related="event_id.user_membership_id.second_key_identification")
    membership_validity = fields.Boolean(related='event_id.membership_validity')
    preference_contact = fields.Selection(related='event_id.preference_contact', readonly=False)

    # MEMBERSHIP FIELD
    display_mask = fields.Char(related="user_membership_id.x_display_mask")
    second_display_mask = fields.Char(related="user_membership_id.x_display_mask_second")
    account_identification_id = fields.Many2one(
        related="user_membership_id.membership_plan_id.account_identification_id")
    second_account_identification_id = fields.Many2one(
        related="user_membership_id.membership_plan_id.second_account_identification_id")
    label_account_identification = fields.Char(related="account_identification_id.label")
    second_label_account_identification = fields.Char(related="second_account_identification_id.label")
    check_second_key = fields.Boolean(related="user_membership_id.membership_plan_id.account_id.x_check_second_key")
    decrypted_key_identification = fields.Char(
        string="Primary Key",
        compute="_compute_decrypted_keys"
    )

    decrypted_second_key_identification = fields.Char(
        string="Secondary Key",
        compute="_compute_decrypted_keys"
    )

    # SERVICE FIELD
    duplicate_service_id = fields.Many2one(related="event_id.service_id")
    service_id = fields.Many2one('product.category')
    service_domain = fields.Binary('Service Domain', compute='_compute_service_domain')
    service_domain_id = fields.Many2one(
        'product.category',
        compute="_compute_service_domain_id",
    )

    sub_service_id = fields.Many2one('product.product', 'Sub-Service')
    duplicate_sub_service_id = fields.Many2one(related='event_id.sub_service_id')

    # LOCATION FIELD
    # location_label = fields.Char('Origin')
    # location_latitude = fields.Char(related="event_id.location_latitude")
    # location_longitude = fields.Char(related="event_id.location_longitude")
    # location_zip_code = fields.Char(related="event_id.location_zip_code")

    # destination_label = fields.Char('Destination')
    # destination_latitude = fields.Char()
    # destination_longitude = fields.Char()
    # destination_zip_code = fields.Char(size=10)

    # BOOLEAN FIELDS
    duplicate_user_data = fields.Boolean(string="Nu data")
    duplicate_policy = fields.Boolean(string="Policy")
    duplicate_vin = fields.Boolean(string="VIN")
    duplicate_service = fields.Boolean(string="Service")
    duplicate_subservice = fields.Boolean(string="Sub-Service")
    duplicate_location = fields.Boolean(string="Origin")
    duplicate_destination = fields.Boolean(string="Destination")

    # COMPUTE
    @api.depends('service_id')
    def _compute_service_domain(self):
        exclude_services = [
            self.env.ref('product.product_category_all').id,
            self.env.ref('product.product_category_1').id,
            self.env.ref('product.cat_expense').id
        ]
        self.service_domain = [
            ('disabled', '=', False),
            ('id', 'not in', exclude_services),
            ('x_input_res_model', '!=', False),
        ]

    @api.depends(
        "event_id.user_membership_id.key_identification",
        "event_id.user_membership_id.second_key_identification"
    )
    def _compute_decrypted_keys(self):
        encryption = self.env['custom.model.encryption']

        for rec in self:
            rec.decrypted_key_identification = False
            rec.decrypted_second_key_identification = False

            if rec.key_identification:
                rec.decrypted_key_identification = encryption.x_decrypt_aes256(
                    rec.key_identification
                )

            if rec.second_key_identification:
                rec.decrypted_second_key_identification = encryption.x_decrypt_aes256(
                    rec.second_key_identification
                )

    @api.depends('duplicate_service', 'service_id', 'event_id.service_id')
    def _compute_service_domain_id(self):
        for rec in self:
            if rec.duplicate_service:
                rec.service_domain_id = rec.event_id.service_id
            else:
                rec.service_domain_id = rec.service_id

    def action_duplicate_event(self):
        self.ensure_one()
        event_id = self.event_id
        vals = {}

        # NU DATA
        # Siempre conservar el NU
        if self.duplicate_user_data:
            vals.update({
                'user_id': event_id.user_id.id if event_id.user_id else False,
                'nu_name': event_id.nu_name,
                'user_membership_id': event_id.user_membership_id.id if event_id.user_membership_id else False,
                'preference_contact': event_id.preference_contact,
            })
        else:
            vals.update({
                'user_id': False,
                'nu_name': False,
                'user_membership_id': False,
                'preference_contact': False,
            })

        # SERVICE
        if self.duplicate_service:
            vals['service_id'] = self.duplicate_service_id.id
        else:
            vals['service_id'] = self.service_id.id

        # SUBSERVICE
        if self.duplicate_subservice:
            vals['sub_service_id'] = self.duplicate_sub_service_id.id
        else:
            vals['sub_service_id'] = self.sub_service_id.id

        # ORIGIN
        if self.duplicate_location:
            vals.update({
                'location_label': event_id.location_label,
                'location_latitude': event_id.location_latitude,
                'location_longitude': event_id.location_longitude,
                'location_zip_code': event_id.location_zip_code,
            })
        else:
            vals.update({
                'location_label': False,
                'location_latitude': False,
                'location_longitude': False,
                'location_zip_code': False,
            })

        # DESTINATION
        if self.duplicate_destination:
            vals.update({
                'destination_label': event_id.destination_label,
                'destination_latitude': event_id.destination_latitude,
                'destination_longitude': event_id.destination_longitude,
                'destination_zip_code': event_id.destination_zip_code,
            })
        else:
            vals.update({
                'destination_label': False,
                'destination_latitude': False,
                'destination_longitude': False,
                'destination_zip_code': False,
            })

        # CREATE NEW EVENT
        new_event_id = event_id.copy(vals)
        new_event_id.parent_id = event_id.id

        self.get_duplicate_ike_event_membership_authorization(new_event_id)

        # DUPLICATE SERVICE INPUT MODEL
        if self.duplicate_service and event_id.service_res_model and event_id.service_res_id:
            service_res = self.env[event_id.service_res_model].browse(event_id.service_res_id)
            new_service = service_res.copy({
                'event_id': new_event_id.id
            })
            new_event_id.service_res_id = new_service.id

    def get_duplicate_ike_event_membership_authorization(self, new_event_id):
        if not self.duplicate_user_data:
            new_event_id.write({
                'membership_authorization_id': False,
                'event_coverage_authorizer': False,
                'required_commercial_authorizer': False,
                'membership_authorization_status': False
            })

            return
        if new_event_id.parent_id.membership_authorization_id:
            new_authorization_id = new_event_id.parent_id.membership_authorization_id.copy({
                'event_id': new_event_id.id,
                'state': 'authorized',
            })
            new_event_id.membership_authorization_id = new_authorization_id.id

            new_event_id.write({
                'event_coverage_authorizer': False,
                'required_commercial_authorizer': False,
            })
