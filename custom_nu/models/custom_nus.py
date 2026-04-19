# -- coding: utf-8 --

from odoo import models, fields, api, _
from markupsafe import Markup
import logging
import time
from datetime import datetime
import requests
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CustomNus(models.Model):
    _name = 'custom.nus'
    _description = 'Custom NUs'
    _inherit = ['custom.model.encryption', 'mail.thread']

    # Original encrypted fields (WITHOUT tracking)
    name = fields.Char(required=True, encrypt=True)
    email = fields.Char(string="Email", encrypt=True)
    phone = fields.Char(string="Phone", encrypt=True, encrypt_search_limit=[-4, None])

    country_id = fields.Many2one(
        comodel_name='res.country', string='Country',
        default=lambda self: self.env.company.country_id)
    complete_phone = fields.Char(string="Complete Phone")
    preference_contact = fields.Selection([
        ('whatsapp', 'WhatsApp'),
        ('message', 'Message'),
        ('email', 'Email'),
    ], string='Preference Contact')

    # Computed fields to display decrypted values in views
    display_complete_phone = fields.Char(
        string='Complete Phone Display',
        store=False
    )

    membership_nus_ids = fields.One2many(
        'custom.membership.nus', 'nus_id', string='Memberships')
    vehicle_nus_ids = fields.One2many(
        'custom.nus.vehicle', 'nus_id', string='Vehicles')
    address_nus_ids = fields.One2many(
        'custom.nus.address', 'nus_id', string='Addresses')
    pet_nus_ids = fields.One2many(
        'custom.nus.pet', 'nus_id', string='Pets')
    vip_user = fields.Boolean(string="VIP User", default=False)
    visa_user = fields.Boolean(string='VISA User', default=False)
    active = fields.Boolean(string='Active', default=True)
    disabled = fields.Boolean(string='Disabled', default=False)

    # === ENCRYPT SEARCH HELPER FIELDS === #
    x_name_search_ids = fields.One2many(
        'custom.nus.search.helper.rel', 'encrypt_model_id',
        domain=[('field_name', '=', 'name')])

    x_phone_search_ids = fields.One2many(
        'custom.nus.search.helper.rel', 'encrypt_model_id',
        domain=[('field_name', '=', 'phone')])

    @api.model_create_multi
    def create(self, vals_list):
        # ToDo: do something with the phone. is necessary?
        return super(CustomNus, self).create(vals_list)

    def write(self, vals):
        # ToDo: do something with the phone. is necessary?
        return super().write(vals)

    # === ACTIONS === #
    def get_token_whatsapp(self):
        parameter = self.env['ir.config_parameter'].sudo()

        token_saved = parameter.get_param('whatsapp.token_access')
        token_expiration_time = parameter.get_param('whatsapp.token_expiration_time')

        if token_saved and token_expiration_time:
            try:
                expiry_timestamp = float(token_expiration_time)
                current_timestamp = time.time()

                if current_timestamp < expiry_timestamp:
                    _logger.info("Using existing WhatsApp token")
                    return token_saved
            except (ValueError, TypeError):
                _logger.warning("Invalid token expiry, requesting new one")

        _logger.info("Requesting new WhatsApp token")

        url = parameter.get_param('whatsapp.login_url')
        username = parameter.get_param('whatsapp.username')
        password = parameter.get_param('whatsapp.password')

        if not all([url, username, password]):
            raise UserError(_(
                "WhatsApp configuration incomplete:\n"
                "- whatsapp.login_url\n"
                "- whatsapp.username\n"
                "- whatsapp.password"
            ))

        try:
            response = requests.post(
                url,
                json={
                    "userName": username,
                    "password": password
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                error_msg = response.json().get('message', 'Unknown error')
                raise UserError(_("Failed to obtain token: %s") % error_msg)

            token_data = response.json().get('data', {})
            token_access = token_data.get('accessToken')
            expires_in = token_data.get('expiresIn', 3600)

            if not token_access:
                raise UserError(_("No access token received"))

            # Guardar token con margen de seguridad (-30 segundos)
            safe_expires_in = max(expires_in - 30, 0)
            expiry_timestamp = time.time() + safe_expires_in

            parameter.set_param('whatsapp.token_access', token_access)
            parameter.set_param('whatsapp.token_expiration_time', str(expiry_timestamp))

            _logger.info("New token saved. Expires: %s", datetime.fromtimestamp(expiry_timestamp))

            return token_access

        except requests.Timeout:
            raise UserError(_("Request timeout"))
        except requests.RequestException as e:
            raise UserError(_("Connection error: %s") % str(e))

    def get_token_sms(self):
        parameter = self.env['ir.config_parameter'].sudo()

        token_access_saved = parameter.get_param('sms.token_access')
        token_expiration_time = parameter.get_param('sms.token_expiration_time')

        if token_access_saved and token_expiration_time:
            try:
                expiry_timestamp = float(token_expiration_time)
                current_timestamp = time.time()

                if current_timestamp < expiry_timestamp:
                    _logger.info("Using existing SMS access token")
                    return token_access_saved

            except (ValueError, TypeError):
                _logger.warning("Invalid token expiry, requesting new one")

        _logger.info("Requesting new SMS token")

        url = parameter.get_param('sms.login_url')
        username = parameter.get_param('sms.username')
        password = parameter.get_param('sms.password')

        if not all([url, username, password]):
            raise UserError(_(
                "SMS configuration incomplete:\n"
                "- sms.login_url\n"
                "- sms.username\n"
                "- sms.password"
            ))

        try:
            response = requests.post(
                url,
                json={
                    "user_name": username,
                    "password": password
                },
                headers={"Content-Type": "application/json"},
                timeout=30
            )

            if response.status_code != 200:
                error_msg = response.json().get('message', response.text)
                raise UserError(_("Failed to obtain token: %s") % error_msg)

            json_resp = response.json()

            token_access = json_resp.get('access_token')
            expires_in = json_resp.get('expires_in', 3600)

            if not token_access:
                raise UserError(_("No access token received"))

            safe_expiration = time.time() + max(expires_in - 30, 0)

            parameter.set_param('sms.token_access', token_access)
            parameter.set_param('sms.token_expiration_time', str(safe_expiration))

            _logger.info("SMS tokens saved. Access token expires at %s", datetime.fromtimestamp(safe_expiration))

            return token_access

        except requests.Timeout:
            raise UserError(_("Request timeout"))

        except requests.RequestException as e:
            raise UserError(_("Connection error: %s") % str(e))

    def action_send_notification_whatsapp(self):
        token = self.get_token_whatsapp()

        parameter = self.env['ir.config_parameter'].sudo()
        url = parameter.get_param('whatsapp.template_url')

        if not url:
            raise UserError(_(
                "WhatsApp configuration incomplete:\n"
                "- whatsapp.template_url"
            ))

        encryption_util = self.env['custom.encryption.utility']

        phone_number = encryption_util.decrypt_aes256(self.phone) if self.phone else False

        if not phone_number:
            raise UserError(_("No phone number available for WhatsApp"))

        headers = {
            "Authorization": f"{token}",
            "Content-Type": "application/json"
        }
        payload = {
            "identifier": {
                "appId": 2,
                "tenants": "adff7f6a-e97d-11eb-9a03-0242ac130003",
                "reference": "18085269"
            },
            "petition": {
                "phoneNumber": phone_number,
                "templateId": 7,
                "templateParameters": [
                    {"parameter": "Arrastre de grúa"}
                ]
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            try:
                result = response.json()
            except Exception:
                result = {}
            if result.get('code') != 200:
                error_msg = result.get('message', 'Unknown error from WhatsApp API')
                raise UserError(_(error_msg))

            response.raise_for_status()

            return result.get('data', {})

        except requests.RequestException as e:
            raise UserError(_("Error connecting to WhatsApp API: %s") % str(e))

    def action_send_notification_sms(self):
        token = self.get_token_sms()

        parameter = self.env['ir.config_parameter'].sudo()
        url = parameter.get_param('sms.send_message_template_url')

        if not url:
            raise UserError(_(
                "SMS configuration incomplete:\n"
                "- sms.send_message_template_url"
            ))

        encryption_util = self.env['custom.encryption.utility']

        phone_number = encryption_util.decrypt_aes256(self.phone) if self.phone else False

        if not phone_number:
            raise UserError(_("No phone number available for SMS"))

        headers = {
            "Authorization": f"{token}",
            "Content-Type": "application/json"
        }
        payload = {
            "identifier": {
                "tenants": "adff7f6a-e97d-11eb-9a03-0242ac130003",
                "app": 1
            },
            "petition": {
                "message": "Mensaje de prueba",
                "phone": phone_number
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            try:
                result = response.json()
            except Exception:
                result = {}

            if not response.ok:
                error_msg = result.get("error", f"HTTP {response.status_code}")
                raise UserError(_(error_msg))

            if result.get('code') != "200":
                error_msg = result.get('message', 'Unknown error from SMS API')
                raise UserError(_(error_msg))

            return result.get('data', {})

        except requests.RequestException as e:
            raise UserError(_("Error connecting to SMS API: %s") % str(e))

    def action_send_notification_sms_list(self):
        token = self.get_token_sms()

        parameter = self.env['ir.config_parameter'].sudo()
        url = parameter.get_param('sms.send_message_list_template_url')

        if not url:
            raise UserError(_(
                "SMS configuration incomplete:\n"
                "- sms.send_message_list_template_url"
            ))

        encryption_util = self.env['custom.encryption.utility']

        phone_number = encryption_util.decrypt_aes256(self.phone) if self.phone else False
        phone_number_list = [phone_number] if phone_number else []

        # print(phone_number_list)

        if not phone_number:
            raise UserError(_("No phone number available for SMS"))

        headers = {
            "Authorization": f"{token}",
            "Content-Type": "application/json"
        }
        payload = {
            "identifier": {
                "tenants": "adff7f6a-e97d-11eb-9a03-0242ac130003",
                "app": 1
            },
            "petition": {
                "message": "Mensaje de prueba",
                "phone": phone_number_list
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            try:
                result = response.json()
            except Exception:
                result = {}

            if not response.ok:
                error_msg = result.get("error", f"HTTP {response.status_code}")
                raise UserError(_(error_msg))

            if result.get('code') != "200":
                error_msg = result.get('message', 'Unknown error from SMS API')
                raise UserError(_(error_msg))

            return result.get('data', {})

        except requests.RequestException as e:
            raise UserError(_("Error connecting to SMS API: %s") % str(e))

    @api.onchange('phone', 'country_id')
    def _onchange_phone_validation(self):
        if self.phone:
            country_id = self.country_id
            if not country_id:
                country_id = list(self._phone_get_country())[0] if self._phone_get_country() else False
            if not country_id:
                country_id = self.env.company.country_id
            phone_format = self._phone_format(fname='phone', force_format='INTERNATIONAL')
            self.phone = self._phone_format(fname='phone', force_format='INTERNATIONAL') or ""
            self.phone = self.phone.partition(' ')[2] if self.phone.startswith('+') else self.phone
            if not phone_format:
                country_name = country_id.name if country_id else _("unknown")

                return {
                    "warning": {
                        "title": _("Validate Phone"),
                        "message": _("The entered phone number is not valid for country %s", country_name),
                    }
                }


class CustomNusSearchHelperRel(models.Model):
    _name = 'custom.nus.search.helper.rel'
    _inherit = ['custom.model.encryption.search.helper.rel']
    _description = 'Custom nus search helper rel'

    encrypt_model_id = fields.Many2one('custom.nus', ondelete='cascade', index=True, required=True)
    encrypt_helper_id = fields.Many2one('custom.nus.search.helper', ondelete='cascade', index=True, required=True)


class CustomNusSearchHelper(models.Model):
    _name = 'custom.nus.search.helper'
    _inherit = ['custom.model.encryption.search.helper']
    _description = 'Custom nus search helper'

    encrypt_rel_ids = fields.One2many('custom.nus.search.helper.rel', 'encrypt_helper_id')
