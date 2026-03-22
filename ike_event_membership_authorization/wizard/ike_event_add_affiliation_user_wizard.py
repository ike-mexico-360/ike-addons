from odoo import models, fields, api, _
from datetime import datetime
import re


class IkeEventAffiliationUser(models.TransientModel):
    _name = 'ike.add.affiliation.nu'
    _description = 'Add NU User to Event'

    # Event
    event_id = fields.Many2one(
        'ike.event',
        string='event',
    )

    # AFFILIATION
    account_id = fields.Many2one('custom.membership.plan', string="account")
    account_name = fields.Char(related="account_id.name", string="Account")
    account_identification_id = fields.Many2one(
        'custom.account.identification',
        related='account_id.account_id.x_account_identification_id',
        readonly=True
    )
    account_identification_second_id = fields.Many2one(
        'custom.account.identification',
        related='account_id.account_id.x_second_key_identification_id',
        readonly=True
    )
    key_primary = fields.Char(required=True)
    key_second = fields.Char()
    label_identification_primary = fields.Char(related="account_identification_id.label", string="label")
    label_identification_second = fields.Char(related="account_identification_second_id.label")
    clause_primary = fields.Char(string="Clause")
    clause_second = fields.Char(string="Second clause")
    check_second_key = fields.Boolean(related="account_id.account_id.x_check_second_key")
    check_clause = fields.Boolean(related="account_identification_id.clause", string="Clause ")
    check_clause_second = fields.Boolean(related="account_identification_second_id.clause", string="Second Clause")

    check_is_fleet = fields.Boolean(string="Is fleet", readonly=False)
    check_is_special = fields.Boolean(string="Is special", readonly=False)
    vehicle_weight_category_id = fields.Many2one(
        'custom.vehicle.weight.category',
        'Weight Category',
        readonly=False,
        domain="[('disabled', '=', False)]")
    display_key_primary_clause = fields.Char(compute="_onchange_key_clause")
    display_key_second_clause_second = fields.Char(compute="_onchange_key_second_clause_second")

    # USER
    name = fields.Char()
    phone = fields.Char()
    phone_alternative = fields.Char()
    authorization = fields.Boolean(related="account_id.account_id.authorizer")
    user_authorization_affiliation_id = fields.Many2one(
        'res.partner',
        string='Authorizing responsible',
    )
    x_domain_authorization_affiliation = fields.Binary(compute="_compute_x_domain_authorization_affiliation")
    contact_preference = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('message', 'Message'),
    ], default='whatsapp',)

    # FIELDS
    fields_readonly = fields.Boolean(default=False)

    x_validation_pattern = fields.Char(string='Validation pattern', related="account_id.x_validation_pattern")
    x_display_mask = fields.Char(string='Display mask', related="account_id.x_display_mask")
    x_validation_pattern_second = fields.Char(string='Second validation pattern', related="account_id.x_validation_pattern_second")
    x_display_mask_second = fields.Char(string='Second display mask', related="account_id.x_display_mask_second")

    is_policy_account = fields.Boolean(
        compute='_compute_is_policy_account',
        store=False
    )

    # ONCHANGE
    @api.onchange('phone', 'phone_alternative')
    def _onchange_phone_only_numbers(self):
        for field in ['phone', 'phone_alternative']:
            valor = self[field] or ''
            numbers = re.sub(r'[^0-9]', '', valor)
            if valor != numbers:
                self[field] = numbers

    @api.onchange('key_primary')
    def _onchange_key(self):
        # Solo buscar si hay suficientes caracteres
        if self.key_primary and len(str(self.key_primary).strip()) < 3:
            return

        if self.key_second and len(str(self.key_second).strip()) < 3:
            return

        membership = None

        # Buscar por clave primaria
        if self.key_primary:
            membership = self._get_membership(key_primary=self.key_primary)

        # if not membership and self.key_second and self.check_second_key:
        #     membership = self._get_membership(key_second=self.key_second)

        # Actualizar datos si se encuentra la membresía
        if membership:

            # Desencriptar y mostrar TODAS las claves de esta membresía
            encryption = self.env['custom.model.encryption']

            decrypted_primary = encryption.x_decrypt_aes256(
                membership.key_identification
            ) if membership.key_identification else None

            decrypted_second = encryption.x_decrypt_aes256(
                membership.second_key_identification
            ) if membership.second_key_identification else None

            decrypted_name = encryption.x_decrypt_aes256(
                membership.nus_id.name
            ) if membership.nus_id and membership.nus_id.name else None

            decrypted_phone = encryption.x_decrypt_aes256(
                membership.nus_id.phone
            ) if membership.nus_id and membership.nus_id.phone else None

            # Verificar si realmente coincide
            if self.key_primary:
                matches_primary = str(decrypted_primary).strip() == str(self.key_primary).strip() if decrypted_primary else False
                matches_second = str(decrypted_second).strip() == str(self.key_primary).strip() if decrypted_second else False

                if not matches_primary and not matches_second:
                    return

            self.name = decrypted_name
            self.phone = decrypted_phone
            self.clause_primary = membership.clause
            self.clause_second = membership.second_clause
            self.vehicle_weight_category_id = membership.vehicle_weight_category_id
            self.check_is_fleet = membership.check_is_fleet
            self.check_is_special = membership.check_is_special
            self.fields_readonly = True

            if self.key_primary and not self.key_second and decrypted_second:
                self.key_second = decrypted_second

            if self.key_second and not self.key_primary and decrypted_primary:
                self.key_primary = decrypted_primary
        # Bypass para que no limpie el número de teléfono, ya que fué cargado desde BP
        elif self._context.get('created_from_bp'):
            pass
        else:
            self.name = False
            self.phone = False
            self.vehicle_weight_category_id = False
            self.check_is_fleet = False
            self.check_is_special = False
            self.fields_readonly = False
            self.key_second = False

    @api.onchange('key_primary', 'clause_primary')
    def _onchange_key_clause(self):
        for rec in self:
            if rec.key_primary and rec.clause_primary:
                rec.display_key_primary_clause = f"{rec.key_primary}-{rec.clause_primary}"
            else:
                rec.display_key_primary_clause = rec.key_primary or rec.clause_primary or False

    @api.onchange('key_second', 'clause_second')
    def _onchange_key_second_clause_second(self):
        for rec in self:
            if rec.key_second and rec.clause_second:
                rec.display_key_primary_clause = f"{rec.key_second}-{rec.clause_second}"
            else:
                rec.display_key_second_clause_second = rec.key_second or rec.clause_second or False

    # COMPUTE
    @api.depends('user_authorization_affiliation_id')
    def _compute_x_domain_authorization_affiliation(self):
        for rec in self:

            user_authorization_ids = rec.env['res.users'].search([
                # ('supplier_id', '=', self.event_id.service_supplier_ids),
                ('groups_id', 'in', [rec.env.ref('custom_master_catalog.custom_group_event_cabin_supervisor').id])  # type:ignore
            ])
            if user_authorization_ids:
                domain = [
                    ('id', 'in', user_authorization_ids.mapped('partner_id').ids),
                ]
                rec.x_domain_authorization_affiliation = domain
            else:
                rec.x_domain_authorization_affiliation = [('id', '=', -1)]

    @api.depends('account_identification_id')
    def _compute_is_policy_account(self):
        policy = self.env.ref('custom_master_catalog.account_identification_policy')
        for rec in self:
            rec.is_policy_account = (
                rec.account_identification_id == policy
            )

    # ACTION
    def action_save(self):
        self.ensure_one()

        if not self.key_primary and not self.key_second:
            return {'type': 'ir.actions.act_window_close'}

        # Buscar membresía por cualquiera de las dos claves
        membership = self._get_membership(
            key_primary=self.key_primary if self.key_primary else None,
            # ToDo: Se comentó porque comentó Mario que la segunda clave no se usará para la búsqueda.
            # key_second=self.key_second if self.key_second and self.check_second_key else None
        )

        if membership:
            nus_user = membership.nus_id
            nus_affiliation_id = membership

            # Actualizar claves si están vacías
            encryption = self.env['custom.model.encryption']
            if self.key_primary and not membership.key_identification:
                membership.key_identification = encryption.x_encrypt_aes256(self.key_primary)
            # ToDo: Se comentó porque comentó Mario que la segunda clave no se usará para la búsqueda.
            # Ejemplo de un vehículo, el VIN no cambia, pero puedo vender el auto, y el dueño es otro.
            # if self.key_second and not membership.second_key_identification:
            #     membership.second_key_identification = encryption.x_encrypt_aes256(self.key_second)
        else:
            nus_user = self._find_existing_user()
            if not nus_user:
                nus_user = self._create_new_user()

            nus_affiliation_id = self._create_affiliation(nus_user)

        self._new_register_authorization(
            nus_membership=nus_affiliation_id,
            nus_user=nus_user
        )

        self.event_id.write({
            'user_id': nus_user.id,
            'user_membership_id': nus_affiliation_id.id,
            'nu_name': self.name,  # type: ignore
            'user_additional_phone': self.phone_alternative,
            # Limpiando campos temporales
            'temporary_phone': False,
            'temporary_key_indentification': False,
            'temporary_membership_plan_id': False,
        })

        return {'type': 'ir.actions.act_window_close'}

    # FUNCTION
    def _get_membership(self, key_primary=None, key_second=None):
        """Busca membresía por clave primaria y/o secundaria"""
        encryption = self.env['custom.model.encryption']
        membership_ids = self.env['custom.membership.nus'].search([
            ('membership_plan_id', '=', self.account_id.id),
            ('disabled', '=', False)
        ])

        if not membership_ids:
            return False

        for membership in membership_ids:
            decrypted_key_primary = encryption.x_decrypt_aes256(
                membership.key_identification
            ) if membership.key_identification else None

            decrypted_key_second = encryption.x_decrypt_aes256(
                membership.second_key_identification
            ) if membership.second_key_identification else None

            # Comparar con la clave primaria proporcionada
            if key_primary:
                if decrypted_key_primary and str(decrypted_key_primary).strip() == str(key_primary).strip():
                    return membership
                if decrypted_key_second and str(decrypted_key_second).strip() == str(key_primary).strip():
                    return membership

            # Comparar con la clave secundaria proporcionada
            if key_second:
                if decrypted_key_primary and str(decrypted_key_primary).strip() == str(key_second).strip():
                    return membership
                if decrypted_key_second and str(decrypted_key_second).strip() == str(key_second).strip():
                    return membership

        return False

    def _get_name(self, name):
        encryption = self.env['custom.model.encryption']

        decrypted_user = encryption.x_decrypt_aes256(name)

        if decrypted_user:
            return decrypted_user
        return False

    def _get_phone(self, phone):
        encryption = self.env['custom.model.encryption']

        decrypted_user = encryption.x_decrypt_aes256(phone)

        if decrypted_user:
            return decrypted_user

    def _new_register_authorization(self, nus_membership, nus_user):
        self.ensure_one()

        membership_authorization_id = self.env['ike.event.membership.authorization'].create({
            'event_id': self.event_id.id,
            'nus_membership_id': nus_membership.id,
            'nus_id': nus_user.id,
            'phone_nu': self.phone,
            'nu_alternative': self.phone_alternative,
            'preference_contact': self.contact_preference,
            'key_identification': self.key_primary,
            'second_key_identification': self.key_second,
            'clause_primary': self.clause_primary,
            'clause_second': self.clause_second,
            'check_is_fleet': self.check_is_fleet,
            'check_is_special': self.check_is_special,
            'authorizer_id': (
                self.user_authorization_affiliation_id.id
                if self.user_authorization_affiliation_id
                else self.env.user.partner_id.id
            ),
            'request_date': fields.Datetime.now(),
            'state': 'pending_cabine',
        })
        self.event_id.membership_authorization_id = membership_authorization_id.id
        membership_authorization_id.with_context(**self.env.context).action_send_authorization_email()
        return

    def _find_existing_user(self):
        """Buscar usuario existente por nombre o teléfono"""
        if not self.name and not self.phone:
            return False

        nus_users = self.env['custom.nus'].search([])

        for user in nus_users:
            name_decrypted = self._get_name(user.name)
            phone_decrypted = self._get_phone(user.phone)

            if self.name and name_decrypted:
                if str(name_decrypted).strip() == str(self.name).strip():
                    return user

            if self.phone and phone_decrypted:
                if str(phone_decrypted).strip() == str(self.phone).strip():
                    return user

        return False

    def _create_affiliation(self, user_id):
        return self.env['custom.membership.nus'].create({
            'nus_id': user_id.id,
            'membership_plan_id': self.account_id.id,
            'key_identification': self.key_primary,
            'second_key_identification': self.key_second,
            'clause': self.clause_primary,
            'second_clause': self.clause_second,
            'date': fields.Date.today(),
            'display_key_primary_clause': self.display_key_primary_clause,
            'display_key_second_clause_second': self.display_key_second_clause_second
        })

    def _create_new_user(self):
        return self.env['custom.nus'].create({
            'name': self.name,
            'phone': self.phone,
            'preference_contact': self.contact_preference
        })
