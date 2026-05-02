# -*- coding: utf-8 -*-
from datetime import datetime
from odoo.addons.ike_event.models.other_models.ike_event_batcher import event_batcher
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64


class IkeEventMembershipAuthorization(models.Model):
    _name = 'ike.event.membership.authorization'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'NUs Membership Authorization'
    _order = 'id desc'

    # === KEY FIELDS === #
    authorization_reasons_id = fields.Many2one('custom.reason.authorizing.additional.costs')
    event_id = fields.Many2one('ike.event', ondelete='cascade', required=True)
    event_name = fields.Char(related='event_id.name')
    nus_membership_id = fields.Many2one('custom.membership.nus', required=True)
    nus_id = fields.Many2one('custom.nus', string="NUs", required=True)
    authorizer_id = fields.Many2one('res.partner', required=True, string="Supervisor authorizer")
    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
    )
    vehicle_weight_category_id = fields.Many2one(
        'custom.vehicle.weight.category',
        'Weight Category',
        related="nus_membership_id.vehicle_weight_category_id",
        readonly=False,
        domain="[('disabled', '=', False)]")
    account_identification_id = fields.Many2one(
        'custom.account.identification',
        related='account_id.x_account_identification_id',
        readonly=True
    )
    account_identification_second_id = fields.Many2one(
        'custom.account.identification',
        related='account_id.x_second_key_identification_id',
        readonly=True
    )
    label_identification_primary = fields.Char(related="account_identification_id.label", string="label")
    label_identification_second = fields.Char(related="account_identification_second_id.label")

    # === FIELDS ACCOUNT=== #
    name = fields.Char(string="name", compute='_compute_name')
    account_id = fields.Many2one(related="nus_membership_id.membership_plan_id.account_id", string="Account ", store=False)
    account = fields.Char(related="nus_membership_id.membership_plan_id.account_id.name", string="Account")
    key_identification = fields.Char(string="Key identification")
    second_key_identification = fields.Char(string="Second key identification")
    masked_key_identification = fields.Char(
        compute="_compute_masked_keys",
        string="Masked Primary Key"
    )

    masked_second_key_identification = fields.Char(
        compute="_compute_masked_keys",
        string="Masked Second Key"
    )
    x_display_mask = fields.Char(related="nus_membership_id.membership_plan_id.account_id.x_display_mask", store=True)
    x_second_display_mask = fields.Char(related="nus_membership_id.membership_plan_id.account_id.x_display_mask_second", store=True)
    label_identification_primary = fields.Char(
        related="nus_membership_id.membership_plan_id.account_identification_id.label",
        string="label")
    label_identification_second = fields.Char(related="nus_membership_id.membership_plan_id.second_account_identification_id.label")
    clause_primary = fields.Char(string="Clause")
    clause_second = fields.Char(string="Second clause")
    check_clause = fields.Boolean(related="nus_membership_id.membership_plan_id.account_identification_id.clause", string="Clause ")
    check_clause_second = fields.Boolean(
        related="nus_membership_id.membership_plan_id.second_account_identification_id.clause",
        string="Second Clause")
    user_authorization_commercial_affiliation_id = fields.Many2one(
        'res.partner',
        string='Authorizing responsible',
    )
    x_domain_authorization_commercial_affiliation = fields.Binary(compute="_compute_x_domain_authorization_commercial_affiliation")
    x_domain_authorization_supervisor_affiliation = fields.Binary(compute="_compute_x_domain_authorization_supervisor_affiliation")
    from_event_button = fields.Boolean()

    # === FIELDS  NUs=== #
    nus_name = fields.Char(
        string="NUs Name",
        compute="_compute_user_name",
        store=False
    )
    preference_contact = fields.Selection([
        ('whatsapp', 'Whatsapp'),
        ('message', 'Message'),
    ])
    nu_alternative = fields.Char(string="Phone alternative")
    phone_nu = fields.Char(string="Phone")

    # === FIELDS === #
    comment_authorizer = fields.Text(string="Comment")
    check_is_fleet = fields.Boolean(string="Is fleet")
    check_is_special = fields.Boolean(string="Is special")
    check_second_key = fields.Boolean(related="nus_membership_id.membership_plan_id.account_id.x_check_second_key")
    check_commercial_authorization = fields.Boolean(string="Required commercial authorization")
    check_supervisor_authorization = fields.Boolean(string="Required supervisor authorization")
    check_membership_authorizer = fields.Boolean(default=False)

    check_is_event_coordinator = fields.Boolean(compute="_compute_is_event_coodinator")
    check_is_event_cabine = fields.Boolean(compute="_compute_is_event_cabine")
    check_is_event_commercial = fields.Boolean(compute="_compute_is_event_commercial")
    check_is_admin = fields.Boolean(compute="_compute_is_admin")

    screenshot = fields.Binary(
        string="Screenshot",
        attachment=True,
        tracking=True
    )
    affiliation_date_start = fields.Date(related="nus_membership_id.date_start", string="Affiliation date start", readonly=False)
    affiliation_date_end = fields.Date(related="nus_membership_id.date_end", string="Affiliation date end", readonly=False)
    date_range_input = fields.Char(string="Date range", store=False)
    date_range_input_error = fields.Boolean(store=False)
    validity = fields.Date(string='Validity')
    request_date = fields.Datetime()
    authorization_date = fields.Datetime()
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending_commercial', 'Pending Commercial Authorization'),
        ('pending_cabine', 'Pending Cabine Authorization'),
        ('authorized', 'Authorized'),
        ('rejected', 'Rejected'),
    ], default='draft', tracking=True)
    image = fields.Binary(
        string="Image",
        attachment=True,
        help="Upload an image for this authorization",
    )
    image_formatted = fields.Binary(
        string="Formatted Image",
        compute="_compute_image_formatted",
        store=False
    )

    @api.onchange('date_range_input')
    def _onchange_date_range_input(self):
        if not self.date_range_input:
            self.date_range_input_error = False
            return
        raw = self.date_range_input.strip()
        for sep in [' - ', ',']:
            parts = raw.split(sep)
            if len(parts) == 2:
                break
        else:
            parts = raw.split('-') if '/' in raw and raw.count('-') == 1 else []
        if len(parts) != 2:
            self.date_range_input_error = True
            return
        parsed = []
        for part in parts:
            try:
                parsed.append(datetime.strptime(part.strip().replace('/', '-'), '%d-%m-%Y').date())
            except ValueError:
                self.date_range_input_error = True
                return
        self.date_range_input_error = False
        self.affiliation_date_start = parsed[0]
        self.affiliation_date_end = parsed[1]

    def write(self, vals):
        """Override write para trackear cambios en imagen con visualización"""
        result = super().write(vals)

        if 'image' in vals:
            for record in self:
                if record.image:
                    # Create file name
                    filename = f"authorization_image_{record.id}_{fields.Datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

                    # Create attachment with the image
                    attachment = self.env['ir.attachment'].create({
                        'name': filename,
                        'datas': record.image,
                        'res_model': self._name,
                        'res_id': record.id,
                        'type': 'binary',
                        'mimetype': 'image/png',
                    })

                    # Post to Chatter with embedded image
                    record.message_post(
                        body=_(
                            """Image Updated"""
                        ).format(attachment.id, filename, fields.Datetime.now().timestamp()),
                        subject=_("Image Update"),
                        message_type='notification',
                        attachment_ids=[attachment.id],
                    )
                else:
                    record.message_post(
                        body=_('Image removed'),
                        subject=_("Image Update"),
                        message_type='notification',
                    )
        return result

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res['from_event_button'] = self.env.context.get('from_event_button', False)
        return res

    # ONCHANGE

    @api.onchange('check_is_fleet')
    def _onchange_fleet(self):
        if self.check_is_fleet:
            self.check_is_special = False

    @api.onchange('check_is_special')
    def _onchange_special(self):
        if self.check_is_special:
            self.check_is_fleet = False

    # COMPUTE

    @api.depends('image')
    def _compute_image_formatted(self):

        for rec in self:
            image = rec.image

            if not image:
                rec.image_formatted = ''
                continue

            if isinstance(image, bytes):
                image = image.decode('utf-8')

            if isinstance(image, str) and image.startswith("b'"):
                image = image[2:-1]

            rec.image_formatted = image

    @api.depends('nus_membership_id.name')
    def _compute_name(self):
        encryption = self.env['custom.model.encryption']
        for rec in self:
            if rec.nus_membership_id and rec.nus_membership_id.name:
                decrypted = encryption.x_decrypt_aes256(
                    rec.nus_membership_id.name
                )
                rec.name = decrypted or False
            else:
                rec.name = False

    def _compute_is_event_coodinator(self):
        group = self.env.user.has_group('custom_master_catalog.custom_group_event_coordinator')
        for rec in self:
            rec.check_is_event_coordinator = group

    def _compute_is_event_cabine(self):
        group = self.env.user.has_group('custom_master_catalog.custom_group_event_cabin_supervisor')
        for rec in self:
            rec.check_is_event_cabine = group

    def _compute_is_event_commercial(self):
        group = self.env.user.has_group('custom_master_catalog.custom_group_commercial_supervisor')
        for rec in self:
            rec.check_is_event_commercial = group

    def _compute_is_admin(self):
        group = self.env.user.has_group('base.group_system')
        for rec in self:
            rec.check_is_admin = group

    def _compute_masked_keys(self):
        for rec in self:
            rec.masked_key_identification = rec._apply_mask(
                rec.key_identification,
                rec.x_display_mask
            )

            rec.masked_second_key_identification = rec._apply_mask(
                rec.second_key_identification,
                rec.x_second_display_mask
            )

    @api.depends('nus_id', 'nus_id.name')
    def _compute_user_name(self):
        encryption = self.env['custom.model.encryption']
        for rec in self:
            if rec.nus_id and rec.nus_id.name:
                decrypted = encryption.x_decrypt_aes256(
                    rec.nus_id.name
                )
                rec.nus_name = decrypted or False
            else:
                rec.nus_name = False

    @api.depends('nus_membership_id.membership_plan_id.account_id.name')
    def _compute_account_name(self):
        encryption = self.env['custom.model.encryption']
        for rec in self:
            if rec.nus_membership_id and rec.nus_membership_id.membership_plan_id.account_id.name:
                decrypted = encryption.x_decrypt_aes256(
                    rec.nus_membership_id.membership_plan_id.account_id.name
                )
                rec.name = decrypted or False
            else:
                rec.name = False

    @api.depends('authorizer_id')
    def _compute_x_domain_authorization_supervisor_affiliation(self):
        for rec in self:

            user_authorization_ids = rec.env['res.users'].search([
                # ('supplier_id', '=', self.event_id.service_supplier_ids),
                ('groups_id', 'in', [rec.env.ref('custom_master_catalog.custom_group_event_cabin_supervisor').id])  # type:ignore
            ])
            if user_authorization_ids:
                domain = [
                    ('id', 'in', user_authorization_ids.mapped('partner_id').ids),
                ]
                rec.x_domain_authorization_supervisor_affiliation = domain
            else:
                rec.x_domain_authorization_supervisor_affiliation = [('id', '=', -1)]

    @api.depends('user_authorization_commercial_affiliation_id')
    def _compute_x_domain_authorization_commercial_affiliation(self):
        for rec in self:

            user_authorization_ids = rec.env['res.users'].search([
                # ('supplier_id', '=', self.event_id.service_supplier_ids),
                ('groups_id', 'in', [rec.env.ref('custom_master_catalog.custom_group_commercial_supervisor').id])  # type:ignore
            ])
            if user_authorization_ids:
                domain = [
                    ('id', 'in', user_authorization_ids.mapped('partner_id').ids),
                ]
                rec.x_domain_authorization_commercial_affiliation = domain
            else:
                rec.x_domain_authorization_commercial_affiliation = [('id', '=', -1)]

    # ACTIONS
    def action_authorized_membership(self):
        for rec in self:

            rec.event_id.write({
                'event_coverage_authorizer': True,
                'required_commercial_authorizer': False
            })
            rec.write({
                'state': 'authorized'
            })
            rec.action_ike_event_reload()
        if self.check_is_event_commercial:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Autorizaciones',
                'res_model': 'ike.event.membership.authorization',
                'view_mode': 'list,form',
                'views': [
                    (self.env.ref('ike_event_membership_authorization.ike_event_membership_authorization_view_list').id, 'list'),
                    (False, 'form'),
                ],
                'target': 'current',
            }

    def action_authorized(self):
        for rec in self:
            rec.event_id.write({
                'required_commercial_authorizer': False
            })
            rec.write({
                'state': 'authorized',
                'authorization_date': fields.Datetime.now(),
                'check_membership_authorizer': False,
                'check_commercial_authorization': False
            })
            rec.nus_membership_id.write({
                'subscription_validity': True,
                'date_start': rec.affiliation_date_start,
                'date_end': rec.affiliation_date_end,
                'check_is_fleet': rec.check_is_fleet,
                'check_is_special': rec.check_is_special,
            })
            rec.action_ike_event_reload()
        if self.check_is_event_commercial:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Autorizaciones',
                'res_model': 'ike.event.membership.authorization',
                'view_mode': 'list,form',
                'views': [
                    (self.env.ref('ike_event_membership_authorization.ike_event_membership_authorization_view_list').id, 'list'),
                    (False, 'form'),
                ],
                'target': 'current',
            }

    def action_ike_event_reload(self):
        self.event_id.broadcastEventReload()
        # for rec in self:
        #     channel_name = f'ike_channel_event_{str(rec.event_id.id)}'
        #     event_batcher.add_event_notification(
        #         self.env.cr.dbname,
        #         channel_name,
        #         'ike_event_membership_info_reload', {
        #             'subscription_validity': True,
        #         },
        #     )

    def action_rejected(self):
        for rec in self:
            rec.write({
                'state': 'rejected',
            })
            rec.nus_membership_id.write({
                'subscription_validity': False
            })
            rec.action_send_authorization_rejected_email()
            rec.action_ike_event_reload()

    def action_authororizer_wizard(self):
        self.ensure_one()
        if self.env.context.get('from_event_button_service'):
            self.write({
                'check_membership_authorizer': True
            })

        if self.check_supervisor_authorization:
            self.write({
                'state': 'pending_cabine'
            })
        if self.check_commercial_authorization:
            self.write({
                'state': 'pending_commercial'
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Authorization'),
            'res_model': 'ike.event.membership.authorization',
            'view_mode': 'form',
            'view_id': self.env.ref(
                'ike_event_membership_authorization.ike_event_membership_authorization_popup_view_form'
            ).id,
            'target': 'new',
            'domain': [('id', '=', self.id)],
            'res_id': self.id,
        }

    def send_mail_commercial_authorizator(self):
        """Send authorization request email to commercial authorizator"""
        self.ensure_one()
        self.write({
            'state': 'pending_commercial',
            'check_commercial_authorization': True
        })
        if self.env.context.get('required_commercial_authorizer'):
            self.event_id.write({'required_commercial_authorizer': True})

        if not self.user_authorization_commercial_affiliation_id or not self.user_authorization_commercial_affiliation_id.email:
            raise UserError(_("The supervisor doesn't have an email address configured."))

        template = self.env.ref(
            'ike_event_membership_authorization.email_template_commercial_authorization_request',
            raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=True)

        return True

    def action_send_authorization_email(self):
        self.ensure_one()

        from_event_button = self.env.context.get('from_event_button')
        if from_event_button:
            self.write({
                'check_membership_authorizer': from_event_button,
                'state': 'pending_cabine'
            })

            self.event_id.write({
                'required_commercial_authorizer': True
            })

            if not self.authorizer_id or not self.authorizer_id.email:
                raise UserError(_("The supervisor doesn't have an email address configured."))

            template = self.env.ref(
                'ike_event_membership_authorization.email_template_authorization_request',
                raise_if_not_found=False
            )

            if template:
                template.send_mail(self.id, force_send=True)

            return True
        self.write({
            'state': 'pending_cabine'
        })

        self.event_id.write({
            'required_commercial_authorizer': True
        })

        if not self.authorizer_id or not self.authorizer_id.email:
            raise UserError(_("The supervisor doesn't have an email address configured."))

        template = self.env.ref(
            'ike_event_membership_authorization.email_template_authorization_request',
            raise_if_not_found=False
        )

        if template:
            template.send_mail(self.id, force_send=True)

        return True

    def get_authorization_url(self):
        self.ensure_one()

        if self.check_commercial_authorization:
            action = self.env.ref(
                'ike_event_membership_authorization.action_membership_commercial_authorization_popup'
            )

            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

            url = f"{base_url}/web#id={self.id}" \
                f"&model=ike.event.membership.authorization" \
                f"&view_type=form" \
                f"&action={action.id}"

            return url

        """Generate authorization URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/odoo/ike-event-screen/{self.event_id.id}"

    def _apply_mask(self, value, mask):
        if not value or not mask:
            return value or ''

        result = ''
        value_index = 0

        for m in mask:
            if m == '#':
                if value_index < len(value):
                    result += value[value_index]
                    value_index += 1
            elif m == '*':
                if value_index < len(value):
                    result += '*'
                    value_index += 1
            else:
                result += m

        return result

    def action_send_authorization_rejected_email(self):
        """Send authorization request email to supervisor"""
        self.ensure_one()
        if not self.authorizer_id or not self.authorizer_id.email:
            raise UserError(_("The supervisor doesn't have an email address configured."))

        # Check if email template exists
        template = self.env.ref(
            'ike_event_membership_authorization.email_template_authorization_request_rejected',
            raise_if_not_found=False
        )
        if not template:
            raise UserError(_("Email template not found."))
        template.send_mail(self.id, force_send=True)

    def get_authorization_rejected_email_to(self):
        self.ensure_one()

        emails = []

        # Si es comercial → enviar a comercial
        if self.check_commercial_authorization and self.authorizer_id:
            emails.append(self.authorizer_id.email)

        return ','.join(emails)
