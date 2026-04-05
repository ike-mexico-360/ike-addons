from odoo import http, _
from odoo.http import request, dispatch_rpc
from odoo.exceptions import ValidationError, UserError
from markupsafe import Markup
from datetime import datetime, timedelta
import re
import requests
import logging
import json
import werkzeug
import time


_logger = logging.getLogger(__name__)


class EventsAPIController(http.Controller):
    # ===============================================================
    # Helpers
    # ===============================================================
    def _generate_ike_token(self, env, scope, expiration_date):
        """Genera una API key nativa de Odoo (res.users.apikeys)."""
        try:
            # Verificación de permisos
            env["res.users.apikeys.description"].check_access_make_key()
            # Genera un nuevo token vinculado al usuario actual
            token = env["res.users.apikeys"]._generate(
                scope=scope,
                name=f"{env.user.login}:{scope}",
                expiration_date=expiration_date + timedelta(seconds=1),
            )
            return token
        except Exception as e:
            _logger.warning(f"[get_ike_token] Error generating API key: {e}")
            return False

    def _validate_refresh_token(self, refresh_token, scope):  # ToDo: ! Unfinished
        """Valida el refresh token existente y devuelve el usuario."""
        api_key_model = request.env["res.users.apikeys"].sudo()

        try:
            # Devuelve la API key si es válida (compara hash internamente)
            rec = api_key_model._check_credentials(refresh_token)
        except Exception:
            _logger.warning("Invalid or unknown refresh token")
            return None

        # Validar el alcance (scope)
        if not rec or rec.scope != f"{scope}_refresh":
            _logger.warning("Invalid scope for refresh token")
            return None

        # Verificar expiración
        # if rec.expiration_date and rec.expiration_date < datetime.now():
        #     _logger.info(f"Refresh token expired for user {rec.user_id.login}")
        #     rec.unlink()  # limpiar tokens vencidos
        #     return None
        return rec.user_id

    @staticmethod
    def x_ike_validate_account_ref_format(code: str) -> bool:
        pattern = r'^[A-Z]{4}-\d{3}$'
        return bool(re.match(pattern, code))

    # ===============================================================
    # Token Generators
    # ===============================================================
    def get_ike_tokens(self, username, password, scope, expiration_date, refresh_expiration_date=None):
        """Genera par accessToken + refreshToken usando la API key interna."""
        empty_token = {
            "accessToken": False,
            "expiresIn": 0,
            "refreshToken": False,
            "tokenType": "Bearer",
            "idToken": False,  # ? Not implemented
            "newDeviceMetadata": False,  # ? Not implemented
        }

        if not username or not password:
            return empty_token

        if not refresh_expiration_date:
            refresh_expiration_date = datetime.now() + timedelta(days=30)

        try:
            uid = dispatch_rpc('common', 'authenticate', [request.db, username, password, {}])
            if not uid:
                _logger.warning("Invalid credentials")
                return empty_token

            env = request.env(user=request.env["res.users"].browse(uid))

            # Generar Access y Refresh Tokens
            access_token = self._generate_ike_token(env, scope, expiration_date)
            refresh_token = self._generate_ike_token(env, f"{scope}_refresh", refresh_expiration_date)
            if not access_token or not refresh_token:
                return empty_token

            expires_in = int((expiration_date - datetime.now()).total_seconds())

            return {
                "accessToken": access_token,
                "expiresIn": expires_in,
                "refreshToken": refresh_token,
                "tokenType": "Bearer",
                "idToken": "eyJraWQiOiJxR294eURGRGhiTGFRQ250TGNSMWNlSGQ2RnBNVkZtTkR",  # ? Not implemented
                "newDeviceMetadata": False,  # ? Not implemented
            }

        except Exception as e:
            _logger.warning(f"[get_ike_tokens] Error: {e}")
            return empty_token

    def refresh_ike_token(self, refresh_token, scope):
        """Simula el flujo OAuth2: usa refreshToken para emitir nuevo accessToken."""
        empty_token = {
            "accessToken": False,
            "expiresIn": 0,
            "refreshToken": False,
            "tokenType": "Bearer",
            "idToken": False,  # ? Not implemented
            "newDeviceMetadata": False,  # ? Not implemented
        }

        try:
            user = self._validate_refresh_token(refresh_token, scope)
            if not user:
                return empty_token

            env = request.env(user=user)

            # Nuevo access token con duración corta (2h)
            new_expiration = datetime.now() + timedelta(hours=2)
            access_token = self._generate_ike_token(env, scope, new_expiration)
            if not access_token:
                return empty_token

            expires_in = int((new_expiration - datetime.now()).total_seconds())

            # Se puede conservar el mismo refresh_token mientras no expire
            return {
                "accessToken": access_token,
                "expiresIn": expires_in,
                "refreshToken": refresh_token,
                "tokenType": "Bearer",
                "idToken": "eyJraWQiOiJxR294eURGRGhiTGFRQ250TGNSMWNlSGQ2RnBNVkZtTkR",  # ? Not implemented
                "newDeviceMetadata": False,  # ? Not implemented
            }

        except Exception as e:
            _logger.warning(f"[refresh_ike_token] Error: {e}")
            return empty_token

    # ===============================================================
    # Routes
    # ===============================================================
    @http.route("/event/getToken", type="http", auth="public", methods=["POST"], csrf=False)
    def event_get_token(self, **kwargs):
        """Recibe username y password, devuelve access + refresh tokens."""
        try:
            data = json.loads(request.httprequest.data.decode("utf-8"))
        except Exception:
            return request.make_json_response({"error": "Invalid JSON"}, status=400)

        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return request.make_json_response({"error": "Credentials not valid"}, status=401)

        expiration_date = datetime.now() + timedelta(days=2)
        refresh_expiration_date = datetime.now() + timedelta(days=30)

        token_data = self.get_ike_tokens(
            username, password, scope="event/getToken",
            expiration_date=expiration_date,
            refresh_expiration_date=refresh_expiration_date,
        )

        if not token_data["accessToken"]:
            return request.make_json_response({"error": "Invalid credentials or server error"}, status=401)
        return request.make_json_response(token_data, status=200)

    # ToDo: Implement refresh token
    # @http.route("/event/refreshToken", type="http", auth="public", methods=["POST"], csrf=False)
    # def event_refresh_token(self, **kwargs):
    #     """Recibe refreshToken, devuelve nuevo accessToken."""
    #     try:
    #         data = json.loads(request.httprequest.data.decode("utf-8"))
    #     except Exception:
    #         return request.make_json_response({"error": "Invalid JSON"}, status=400)

    #     refresh_token = data.get("refreshToken")
    #     if not refresh_token:
    #         return request.make_json_response({"error": "Missing refresh token"}, status=400)

    #     new_token_data = self.refresh_ike_token(refresh_token, scope="event/getToken")
    #     if not new_token_data["accessToken"]:
    #         return request.make_json_response({"error": "Invalid or expired refresh token"}, status=401)
    #     return request.make_json_response(new_token_data, status=200)

    # ToDo: General
    # Refactorizar historyService & newEvent, la forma de hacer match y validar los datos es similar,
    # unificar en una función reutilizable para ambos, son las mismas reglas, a diferencia del user_bp
    # por temas de tiempo se copia y pega por la urgenica y premura de tenerlo
    # ! Importante refactorizar para tener simple y limpio el código
    @http.route('/event/historyService', type='http', auth='public', methods=['POST'], csrf=False)
    def ike_event_history_service(self, **kwargs):
        # === Autorización ===
        # ToDo: Mover mx_tenant fuera, ya sea como parámetro o un ajuste en la configuración
        mx_tenant = "adff7f6a-e97d-11eb-9a03-0242ac130003"
        headers = request.httprequest.headers
        authorization = headers.get('Authorization')
        if not authorization:
            _logger.warning('Unauthorized')
            return request.make_json_response({'error': 'Unauthorized'}, status=401)
        if authorization.startswith("Bearer "):
            authorization = authorization[7:]

        # === Datos de la petición ===
        json_data = request.get_json_data() or {}
        identifier = json_data.get('identifier', {})
        petition = json_data.get('petition', {})

        if not identifier or not petition:
            _logger.warning('Bad request')
            return request.make_json_response({'error': 'Bad request'}, status=400)
        if identifier.get('tenants', '') != mx_tenant:
            _logger.warning('Bad request')
            return request.make_json_response({'error': 'Bad request'}, status=400)

        # === Validar petición ===
        phone = str(petition.get('phone', '') or '').strip().replace(' ', '')
        account = str(petition.get('account', '') or '').strip().replace(' ', '')  # Deberá sr el valor de la referencia de la cuenta, ejemplo PRSE -> PRIMERO SEGUROS
        key = petition.get('key', False)  # Opcional
        try:  # Opcional, por default 1, se completará a 3 ceros, ejemplo 001
            call_type = int(petition.get('type', 1))
        except (ValueError, TypeError):
            call_type = 1
        if not (1 <= call_type <= 999):
            call_type = 1

        if not phone or not account:
            _logger.warning('Bad request')
            return request.make_json_response({'error': 'Bad request'}, status=400)
        # Se forma la clave de la referencia, ejemplo:
        #   PRSE-001 -> PRIMERO SEGUROS
        #   PRSE-002 -> PRIMERO SEGUROS PESADOS
        account_ref = f"{account.upper()}-{str(call_type).zfill(3)}"
        # ToDo: Cuando sea primero seguros, ignorar el valor de key
        if account_ref in ['PRSE-001', 'PRSE-002']:
            key = False
        valid_account_ref = self.x_ike_validate_account_ref_format(account_ref)
        if not valid_account_ref:
            _logger.warning(f'Bad request account ref {account_ref}')
            return request.make_json_response({'error': 'Bad request account'}, status=400)

        # === Validar token ===
        api_key_model = request.env["res.users.apikeys"].sudo()
        try:
            uid = api_key_model._check_credentials(scope='event/getToken', key=authorization)
        except Exception:
            _logger.warning("Invalid or unknown refresh token")
            uid = None

        if not uid:
            _logger.warning('Unauthorized')
            return request.make_json_response({'error': 'Unauthorized'}, status=401)

        _logger.info(f"/event/historyService/{account_ref}/{phone}")

        # Buscar NU: affiliate validation
        decrypt_encrypt_utility_sudo = request.env['custom.encryption.utility'].sudo()

        nu_data = False
        affiliation_data = False
        plan_data = False

        plan_query = """
            SELECT
                plan.id AS id,
                plan.name AS name
            FROM
                custom_membership_plan plan
            WHERE
                plan.bp_account_ref = %s
            ORDER BY plan.id DESC
            LIMIT 1;
        """
        request.env.cr.execute(plan_query, (account_ref,))
        plan_data = request.env.cr.dictfetchone()

        if not plan_data:
            _logger.warning('Not found: No matching account (Plan)')
            return request.make_json_response({}, status=200)

        query = """
            SELECT
                -- Affiliation fields (custom.membership.nus)
                jsonb_build_object(
                    'id', affiliation.id,
                    'key_identification', affiliation.key_identification
                ) AS affiliation,
                -- NU fields (custom.nus)
                jsonb_build_object(
                    'id', nu.id,
                    'name', nu.name,
                    'phone', nu.phone,
                    'complete_phone', nu.complete_phone,
                    'vip_user', nu.vip_user
                ) AS nu
            FROM
                custom_membership_nus affiliation
            INNER JOIN
                custom_nus nu ON nu.id = affiliation.nus_id
            WHERE
                affiliation.membership_plan_id = %s
                AND affiliation.disabled = false
            ORDER BY affiliation.id DESC;
        """
        request.env.cr.execute(query, (plan_data['id'],))
        # Separar, primero buscar account, y validar si existe el account y entonces buscar lo demás
        records = request.env.cr.dictfetchall()
        # ToDo: Integrar búsqueda con los campos de búsqueda de encriptación
        for record in records:
            affiliation = record['affiliation']
            plan = plan_data
            nu = record['nu']
            phone_dec = decrypt_encrypt_utility_sudo.decrypt_aes256(str(nu['phone']) if nu['phone'] else '')
            complete_phone_dec = decrypt_encrypt_utility_sudo.decrypt_aes256(str(nu['complete_phone']) if nu['complete_phone'] else '')
            if complete_phone_dec:
                complete_phone_dec = complete_phone_dec.replace(' ', '')  # Eliminar espacios en números formateados
            if phone_dec:
                phone_dec = phone_dec.replace(' ', '')  # Eliminar espacios en números formateados
            key_identification_dec = decrypt_encrypt_utility_sudo.decrypt_aes256(str(affiliation['key_identification']) if affiliation['key_identification'] else '')
            if key_identification_dec:
                key_identification_dec = key_identification_dec.replace(' ', '')  # Eliminar espacios en números formateados

            if key and key_identification_dec == key and complete_phone_dec == f"+52{phone}":
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account, key identification and complete_phone")
                break
            # ToDo: Quitar este caso, debe ser con complete_phone, se añade porque complete_phone no está guardando correctamente
            elif key and key_identification_dec == key and f"+52{phone_dec}" == f"+52{phone}":
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account, key identification and phone")
                break
            elif key and key_identification_dec == key:
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account and key identification")
                break
            elif complete_phone_dec == f"+52{phone}":
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account and complete_phone")
                break
            # ToDo: Quitar este caso, debe ser con complete_phone, se añade porque complete_phone no está guardando correctamente
            elif f"+52{phone_dec}" == f"+52{phone}":
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account and phone")
                break

        if not nu_data:
            _logger.warning('Not found: No matching account (NU)')
            return request.make_json_response({}, status=200)

        if not affiliation_data:
            _logger.warning('Not found: No matching account (Affiliation)')
            # return request.make_json_response({'error': 'Not found: No matching account (Membership)'}, status=400)

        user_tz = request.env.user.tz or 'UTC'
        user_lang = request.env.user.lang or 'en_US'
        user_id = nu_data['id']
        nu_name = decrypt_encrypt_utility_sudo.decrypt_aes256(nu_data['name'] if nu_data else '')
        history_query = """
            SELECT
                ie.id::TEXT AS "id",
                '' AS "key",
                ie.name::TEXT AS "idExpedient",
                plan.name::TEXT AS "accountName",
                service.id::TEXT AS "idService",
                service.name::TEXT AS "serviceName",
                COALESCE(subservice.id::TEXT, '') AS "idSubService",
                COALESCE(pt.name->>%(user_lang)s, pt.name->>'en_US', '') AS "subServiceName",
                stage.id::TEXT AS "idStatus",
                COALESCE(stage.name->>%(user_lang)s, stage.name->>'en_US', '') AS "statusName",
                to_char((ie.event_date AT TIME ZONE 'UTC') AT TIME ZONE %(user_tz)s, 'YYYY-MM-DD"T"HH24:MI:SS.US') AS "registrationDate"
            FROM ike_event ie
            INNER JOIN custom_membership_nus membership ON membership.id = ie.user_membership_id
            INNER JOIN custom_membership_plan plan ON plan.id = membership.membership_plan_id
            INNER JOIN product_category service ON service.id = ie.service_id
            LEFT JOIN product_product subservice ON subservice.id = ie.sub_service_id
            LEFT JOIN product_template pt ON pt.id = subservice.product_tmpl_id
            INNER JOIN ike_event_stage stage ON stage.id = ie.stage_id
            WHERE ie.user_id = %(user_id)s;
        """
        request.env.cr.execute(history_query, {'user_id': user_id, 'user_lang': user_lang, 'user_tz': user_tz})
        events = request.env.cr.dictfetchall()
        return request.make_json_response({
            "nameUser": nu_name,
            "historyService": events
        }, status=200)

    @http.route('/event/newEvent', type='http', auth='public', methods=['POST'], csrf=False)
    def ike_event_new_event(self, **kwargs):
        # === Autorización ===
        # ToDo: Mover mx_tenant fuera, ya sea como parámetro o un ajuste en la configuración
        mx_tenant = "adff7f6a-e97d-11eb-9a03-0242ac130003"
        headers = request.httprequest.headers
        authorization = headers.get('Authorization')
        if not authorization:
            _logger.warning('Unauthorized')
            return request.make_json_response({'error': 'Unauthorized'}, status=401)
        if authorization.startswith("Bearer "):
            authorization = authorization[7:]

        # === Datos de la petición ===
        json_data = request.get_json_data() or {}
        identifier = json_data.get('identifier', {})
        petition = json_data.get('petition', {})

        if not identifier or not petition:
            _logger.warning('Bad request')
            return request.make_json_response({'error': 'Bad request'}, status=400)
        if identifier.get('tenants', '') != mx_tenant:
            _logger.warning('Bad request')
            return request.make_json_response({'error': 'Bad request'}, status=400)

        # === Validar petición ===
        phone = str(petition.get('phone', '') or '').strip().replace(' ', '')
        account = str(petition.get('account', '') or '').strip().replace(' ', '')  # Deberá sr el valor de la referencia de la cuenta, ejemplo PRSE -> PRIMERO SEGUROS
        # ToDo: UserBP puede ser buscado directo a res.users con el login y tomar el campo parent_id que es el res.partner
        user_bp = str(petition.get('user_bp', '') or '').strip().replace(' ', '')
        key = petition.get('key', False)  # Opcional
        try:  # Opcional, por default 1, se completará a 3 ceros, ejemplo 001
            call_type = int(petition.get('type', 1))
        except (ValueError, TypeError):
            call_type = 1
        if not (1 <= call_type <= 999):
            call_type = 1

        if not phone or not account or not user_bp:
            _logger.warning('Bad request')
            return request.make_json_response({'error': 'Bad request'}, status=400)
        # Se forma la clave de la referencia, ejemplo:
        #   PRSE-001 -> PRIMERO SEGUROS
        #   PRSE-002 -> PRIMERO SEGUROS PESADOS
        account_ref = f"{account.upper()}-{str(call_type).zfill(3)}"
        # ToDo: Cuando sea primero seguros, ignorar el valor de key
        if account_ref in ['PRSE-001', 'PRSE-002']:
            key = False
        valid_account_ref = self.x_ike_validate_account_ref_format(account_ref)
        if not valid_account_ref:
            _logger.warning(f'Bad request account ref {account_ref}')
            return request.make_json_response({'error': 'Bad request account'}, status=400)

        # === Validar token ===
        api_key_model = request.env["res.users.apikeys"].sudo()
        try:
            uid = api_key_model._check_credentials(scope='event/getToken', key=authorization)
        except Exception:
            _logger.warning("Invalid or unknown refresh token")
            uid = None

        if not uid:
            _logger.warning('Unauthorized')
            return request.make_json_response({'error': 'Unauthorized'}, status=401)

        _logger.info(f"/event/newEvent/{account_ref}/{phone}/{user_bp}")

        # User query: user_BP
        user_id_BP = "select partner_id from res_users where login = %s"

        request.env.cr.execute(user_id_BP, (user_bp,))
        user_id_data = request.env.cr.dictfetchone()

        if not user_id_data:
            _logger.warning('Not found: No matching account (Plan)')
            return request.make_json_response({'error': 'Not found: No matching account (Plan)'}, status=400)

        # Buscar NU: affiliate validation
        decrypt_encrypt_utility_sudo = request.env['custom.encryption.utility'].sudo()

        nu_data = False
        affiliation_data = False
        plan_data = False

        plan_query = """
            SELECT
                plan.id AS id,
                plan.name AS name
            FROM
                custom_membership_plan plan
            WHERE
                plan.bp_account_ref = %s
            ORDER BY plan.id DESC
            LIMIT 1;
        """
        request.env.cr.execute(plan_query, (account_ref,))
        plan_data = request.env.cr.dictfetchone()

        if not plan_data:
            _logger.warning('Not found: No matching account (Plan)')
            return request.make_json_response({'error': 'Not found: No matching account (Plan)'}, status=400)

        query = """
            SELECT
                -- Affiliation fields (custom.membership.nus)
                jsonb_build_object(
                    'id', affiliation.id,
                    'key_identification', affiliation.key_identification
                ) AS affiliation,
                -- NU fields (custom.nus)
                jsonb_build_object(
                    'id', nu.id,
                    'name', nu.name,
                    'phone', nu.phone,
                    'complete_phone', nu.complete_phone,
                    'vip_user', nu.vip_user
                ) AS nu
            FROM
                custom_membership_nus affiliation
            INNER JOIN
                custom_nus nu ON nu.id = affiliation.nus_id
            WHERE
                affiliation.membership_plan_id = %s
                AND affiliation.disabled = false
            ORDER BY affiliation.id DESC;
        """
        request.env.cr.execute(query, (plan_data['id'],))
        # Separar, primero buscar account, y validar si existe el account y entonces buscar lo demás
        records = request.env.cr.dictfetchall()
        # ToDo: Integrar búsqueda con los campos de búsqueda de encriptación
        for record in records:
            affiliation = record['affiliation']
            plan = plan_data
            nu = record['nu']
            phone_dec = decrypt_encrypt_utility_sudo.decrypt_aes256(str(nu['phone']) if nu['phone'] else '')
            complete_phone_dec = decrypt_encrypt_utility_sudo.decrypt_aes256(str(nu['complete_phone']) if nu['complete_phone'] else '')
            if complete_phone_dec:
                complete_phone_dec = complete_phone_dec.replace(' ', '')  # Eliminar espacios en números formateados
            if phone_dec:
                phone_dec = phone_dec.replace(' ', '')  # Eliminar espacios en números formateados
            key_identification_dec = decrypt_encrypt_utility_sudo.decrypt_aes256(str(affiliation['key_identification']) if affiliation['key_identification'] else '')
            if key_identification_dec:
                key_identification_dec = key_identification_dec.replace(' ', '')  # Eliminar espacios en números formateados

            if key and key_identification_dec == key and complete_phone_dec == f"+52{phone}":
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account, key identification and complete_phone")
                break
            # ToDo: Quitar este caso, debe ser con complete_phone, se añade porque complete_phone no está guardando correctamente
            elif key and key_identification_dec == key and f"+52{phone_dec}" == f"+52{phone}":
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account, key identification and phone")
                break
            elif key and key_identification_dec == key:
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account and key identification")
                break
            elif complete_phone_dec == f"+52{phone}":
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account and complete_phone")
                break
            # ToDo: Quitar este caso, debe ser con complete_phone, se añade porque complete_phone no está guardando correctamente
            elif f"+52{phone_dec}" == f"+52{phone}":
                nu_data = nu
                affiliation_data = affiliation
                plan_data = plan
                _logger.warning(f"Membership: {affiliation['id']}: Matching account and phone")
                break

        if not nu_data:
            _logger.warning('Not found: No matching account (NU)')
            # return request.make_json_response({'error': 'Not found: No matching account (NU)'}, status=400)

        if not affiliation_data:
            _logger.warning('Not found: No matching account (Affiliation)')
            # return request.make_json_response({'error': 'Not found: No matching account (Membership)'}, status=400)

        # Crear evento
        try:
            nu_name = decrypt_encrypt_utility_sudo.decrypt_aes256(nu_data['name'] if nu_data else '')
            new_event_id = request.env['ike.event'].sudo().create({
                'created_from_bp': True,
                'user_id': nu_data['id'] if nu_data else False,
                'nu_name': nu_name if nu_name else '',
                'user_membership_id': affiliation_data['id'] if affiliation_data else False,
                # ToDo: Se encriptarán estos valores?
                'temporary_phone': phone if not nu_data else '',
                'temporary_key_indentification': key if not affiliation_data else '',
                'temporary_membership_plan_id': plan_data['id'] if not affiliation_data else False,
            })

            # channel = request.env['discuss.channel'].sudo().search([
            #     ('channel_type', '=', 'channel'),
            #     ('name', '=', 'general')
            # ], limit=1)

            user_partner_id = request.env['res.partner'].sudo().browse(user_id_data.get('partner_id'))

            channel = request.env['discuss.channel'].sudo().search([
                ('channel_type', '=', 'chat'),
                ('channel_partner_ids', 'in', [user_partner_id.id]),
            ], limit=1)

            if not channel:
                channel = request.env['discuss.channel'].sudo().search([
                    ('channel_type', '=', 'channel'),
                    ('name', '=', 'general')
                ], limit=1)

            if channel:
                author_id = request.env.ref('base.user_root')
                base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
                url = f"{base_url}/odoo/ike-event-screen/{new_event_id.id}"
                vip_user = nu_data['vip_user'] if nu_data else False
                vip_message = Markup("""
                <span class="badge mb-2 rounded-pill text-bg-success ps-1 pe-2 py-1">
                    <i class="fa fa-star"/> Cliente VIP
                </span>""")
                body = Markup("""
                    <h3>Evento creado</h3>
                    {}
                    <div>
                        <strong>Usuario: </strong> {}
                    </div>
                    <div>
                        <strong>Cuenta: </strong> {}
                    </div>
                    <div>
                        <strong>Evento: </strong> <a href="{}" target="_blank">{}</a>
                    </div>
                """).format(
                    vip_message if vip_user else '',
                    nu_name,
                    plan_data['name'] if plan_data else '',
                    url,
                    new_event_id.name,
                )
                channel.sudo().message_post(
                    body=body,
                    message_type='comment',
                    author_id=author_id.id,
                    subtype_xmlid='mail.mt_comment',
                    body_is_html=True)
            else:
                _logger.warning('Canal general no encontrado, notificación omitida')

            _logger.info(f'Event created: {new_event_id.name}')
            return request.make_json_response({
                "nameUser": nu_name,
                "historyService": [
                    {
                        "id": "1",
                        "key": new_event_id.id,
                        "idExpedient": new_event_id.name,
                        "idAccount": affiliation_data['id'] if affiliation_data else False,
                        "accountName": plan_data['name'] if plan_data else '',
                        "idService": "1",
                        "serviceName": "Asistencia Vial",
                        "idSubService": "211",
                        "subServiceName": "Arrastre de Grúa",
                        "idStatus": "10",
                        "statusName": "Concluido",
                        "registrationDate": new_event_id.create_date.isoformat() if new_event_id.create_date else None
                    },
                ],
                "coverage": [
                    {
                        "idService": "10",
                        "serviceName": "Asistencia Vial",
                        "idSubService": "214",
                        "subServiceName": "Suministro de Gasolina",
                        "status": "CUBIERTOS"
                    }
                ]
            }, status=200)
        except Exception as e:
            _logger.warning(f'Error creando evento: {str(e)}')
            return request.make_json_response({'error': 'Error at create'}, status=500)

    @http.route('/openai/assistant/call', type='http', auth='user', methods=['POST'], csrf=False)
    def call_assistant(self, **kwargs):
        """Endpoint para llamar al OpenAI Assistant"""
        open_ai_base_url = 'https://api.openai.com/v1'
        thread_id = None
        headers = {}
        try:
            # Obtener datos del request
            survey = request.get_json_data() or {}

            # Tu API Key (mejor guardarla en configuración de Odoo)
            api_key = request.env['ir.config_parameter'].sudo().get_param('suggested_trucks.openai.api_key')
            assistant_id = request.env['ir.config_parameter'].sudo().get_param('suggested_trucks.openai.assistant_id')

            if not api_key or not assistant_id or not survey:
                return request.make_json_response({'error': 'Configuración incompleta'}, status=400)

            survey_bad_response = {
                "id": survey.get('id'),
                "suggested_accessories": [],
                "suggested_concepts": [],
                "suggested_vehicle_types": [],
            }

            # Headers para OpenAI
            headers = {
                'Authorization': f'Bearer {api_key}',
                'OpenAI-Beta': 'assistants=v2',
                'Content-Type': 'application/json'
            }

            # 1. Crear un Thread
            thread_response = requests.post(
                f'{open_ai_base_url}/threads',
                headers=headers
            )
            thread_id = thread_response.json().get('id', False)
            if not thread_id:
                _logger.warning('No se pudo crear el thread en OpenAI')
                return request.make_json_response({'error': 'No se pudo crear el thread en OpenAI'}, status=500)

            # 2. Agregar mensaje al Thread
            prompt = '''
                Analiza este caso de asistencia vial. Devuelve solo el JSON final.

                {{ JSON.stringify(%s) }}
            ''' % json.dumps(survey)
            requests.post(
                f'{open_ai_base_url}/threads/{thread_id}/messages',
                headers=headers,
                json={'role': 'user', 'content': prompt}
            )

            # 3. Ejecutar el Assistant
            run_response = requests.post(
                f'{open_ai_base_url}/threads/{thread_id}/runs',
                headers=headers,
                json={'assistant_id': assistant_id}
            )
            run_id = run_response.json().get('id', False)
            if not run_id:
                _logger.warning('No se pudo crear el run en OpenAI')
                return request.make_json_response({'error': 'No se pudo crear el run en OpenAI'}, status=500)

            # 4. Esperar a que se complete (con timeout)
            max_attempts = 30
            attempts = 0

            while attempts < max_attempts:
                run_check = requests.get(
                    f'{open_ai_base_url}/threads/{thread_id}/runs/{run_id}',
                    headers=headers
                ).json()

                status = run_check.get('status', '')
                if status == 'completed':
                    break
                elif status == 'failed':
                    return request.make_json_response({'error': 'El assistant falló en la ejecución'}, status=409)

                time.sleep(1)
                attempts += 1
            if attempts >= max_attempts:
                return request.make_json_response({'error': 'Timeout esperando al assistant'}, status=504)

            # 5. Obtener los mensajes
            messages_response = requests.get(
                f'{open_ai_base_url}/threads/{thread_id}/messages',
                headers=headers
            ).json()

            # Obtener la última respuesta del assistant
            assistant_message = None
            for msg in messages_response.get('data', []):
                if msg['role'] == 'assistant':
                    assistant_message = msg['content'][0]['text']['value']
                    break

            if not assistant_message:
                return request.make_json_response(survey_bad_response, status=200)

            try:
                json_response = json.loads(assistant_message)
            except json.JSONDecodeError:
                _logger.warning(f'Respuesta no parseable del assistant: {assistant_message}')
                return request.make_json_response(survey_bad_response, status=200)

            return request.make_json_response(json_response, status=200)

        except Exception as e:
            _logger.warning(f'Error en llamar al assistant: {str(e)}')
            return request.make_json_response({'error': 'Error en el servidor'}, status=500)
        finally:
            # Eliminar el thread
            if thread_id:
                try:
                    requests.delete(f'{open_ai_base_url}/threads/{thread_id}', headers=headers)
                except Exception:
                    pass

    @http.route('/api/v1/client', type='json', auth='user', methods=['POST'], csrf=False)
    def ike_api_v1_client_create(self, **kwargs):
        """
        Endpoint para crear registros de cliente
        Recibe datos en formato JSON y crea el registro correspondiente
        """
        response = self._ike_api_v1_create_partner(kwargs, 'client')
        return response

    @http.route('/api/v1/supplier', type='json', auth='user', methods=['POST'], csrf=False)
    def ike_api_v1_supplier_create(self, **kwargs):
        """
        Endpoint para crear registros de proveedor
        Recibe datos en formato JSON y crea el registro correspondiente
        """
        response = self._ike_api_v1_create_partner(kwargs, 'supplier')
        return response

    # ToDo: Quitar cuando Charly notifique que ya no lo ocupa
    @http.route('/api/v1/meta', type='http', auth='public', methods=['POST'], csrf=False)
    def ike_api_v1_meta(self, **kwargs):
        """
        Endpoint público: recibe un JSON y lo devuelve tal cual. Pruebas de Charly
        """
        try:
            json_data = request.get_json_data() or {}
            return request.make_json_response(
                json_data,
                status=200
            )
        except (ValueError, TypeError):
            return request.make_json_response(
                {"error": "Invalid JSON"},
                status=400
            )

    def _ike_api_v1_create_partner(self, kwargs, partner_type=None):
        def _validate_rfc(rfc):
            """Validar formato de RFC mexicano"""
            if not rfc:
                return False
            return len(rfc) in [12, 13] and rfc.isalnum()

        def _validate_email(email):
            """Validación básica de email"""
            import re
            pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            return re.match(pattern, email) is not None

        def _sanitize_data(data):
            """Sanitizar datos de entrada"""
            sanitized = {}
            for key, value in data.items():
                if isinstance(value, str):
                    sanitized[key] = value.strip()
                else:
                    sanitized[key] = value
            return sanitized

        try:
            if partner_type is None:
                raise werkzeug.exceptions.BadRequest('Tipo de registro no especificado')
            # Validación de autenticación
            if not request.env.uid:
                request.env.cr.rollback()
                raise werkzeug.exceptions.Unauthorized('Usuario no autenticado')

            # Obtener datos del request
            data = kwargs or request.params

            # Validación de campos obligatorios
            required_fields = {
                'ref': {'type': 'CHAR', 'max_legth': 10, 'odoo_field': 'x_ref_sap'},
                'name': {'type': 'CHAR', 'max_legth': 40, 'odoo_field': 'name'},
                'society': {'type': 'CHAR', 'max_legth': 4, 'odoo_field': 'x_society_sap'},
                'town': {'type': 'CHAR', 'max_legth': 40, 'odoo_field': 'city'},
                'state': {'type': 'CHAR', 'max_legth': 3, 'odoo_field': 'state_id'},
                'rfc': {'type': 'CHAR', 'max_legth': 60, 'odoo_field': 'vat'},
                'natural_person': {'type': 'CHAR', 'max_legth': 1, 'odoo_field': 'company_type'}
            }

            optional_fields = {
                'street': {'type': 'CHAR', 'max_legth': 60, 'odoo_field': 'street'},
                'street_number': {'type': 'CHAR', 'max_legth': 10, 'odoo_field': 'street2'},
                'municipality': {'type': 'CHAR', 'max_legth': 40},  # ToDo: A que campo corresponde en Odoo?
                'phone': {'type': 'CHAR', 'max_legth': 30, 'odoo_field': 'phone'},
                'mobile': {'type': 'CHAR', 'max_legth': 16, 'odoo_field': 'mobile'},
                'email': {'type': 'CHAR', 'max_legth': 241, 'odoo_field': 'email'}
            }

            # Validar presencia de campos obligatorios
            missing_fields = [field for field in required_fields.keys() if field not in data]
            if missing_fields:
                raise werkzeug.exceptions.BadRequest(
                    f'Faltan campos obligatorios: {", ".join(missing_fields)}'
                )

            # Sanitizar datos
            sanitized_data = _sanitize_data(data)

            # Validación de longitud de campos
            validation_errors = []
            for field, value in sanitized_data.items():
                if field not in required_fields.keys() and field not in optional_fields.keys():
                    continue
                if field in required_fields:
                    field_type = required_fields[field]['type']
                    max_length = required_fields[field]['max_legth']
                elif field in optional_fields:
                    field_type = optional_fields[field]['type']
                    max_length = optional_fields[field]['max_legth']
                else:
                    continue

                if field_type == 'CHAR':
                    if isinstance(value, str) and len(value) > max_length:
                        validation_errors.append({
                            'field': field,
                            'error': f'Excede longitud máxima de {max_length} caracteres',
                            'current_length': len(value)
                        })
                elif field_type == 'NUM':
                    if not isinstance(value, int):
                        validation_errors.append({
                            'field': field,
                            'error': 'Debe ser un número entero'
                        })
                elif field_type == 'FLOAT':
                    if not isinstance(value, float):
                        validation_errors.append({
                            'field': field,
                            'error': 'Debe ser un número decimal'
                        })
                else:
                    _logger.warning(f'Tipo de campo desconocido: {field_type}')

            if validation_errors:
                raise ValidationError(f'Errores de validación: {validation_errors}')

            # Validación de RFC
            if 'rfc' in sanitized_data:
                rfc = sanitized_data['rfc'].strip().upper()
                if not _validate_rfc(rfc):
                    raise werkzeug.exceptions.UnprocessableEntity(
                        'RFC inválido. Debe tener 12 o 13 caracteres alfanuméricos'
                    )
                sanitized_data['rfc'] = rfc

            # Verificar partner duplicado, vat y x_ref_sap
            existing_partner = request.env['res.partner'].sudo().search([
                ('vat', '=', sanitized_data['rfc']),
                ('x_ref_sap', '=', sanitized_data['ref'])
            ], limit=1)

            if existing_partner:
                raise werkzeug.exceptions.Conflict(
                    f'El RFC {sanitized_data["rfc"]} y Referencia SAP {sanitized_data["ref"]} ya existen en el sistema (ID: {existing_partner.id}, Nombre: {existing_partner.name})'
                )

            # Validación de email
            if 'email' in sanitized_data and sanitized_data['email']:
                if not _validate_email(sanitized_data['email']):
                    raise werkzeug.exceptions.UnprocessableEntity('Formato de email inválido')

            # Campos requeridos
            partner_vals = {k: sanitized_data[k] for k, v in required_fields.items() if v.get('odoo_field', False)}

            # Campos opcionales
            __ = [partner_vals.update({k: sanitized_data[k]}) for k, v in optional_fields.items() if k in sanitized_data and v.get('odoo_field', False)]  # noqa

            # Convertir campos requeridos en campos de Odoo
            for k, v in required_fields.items():
                odoo_field = v.get('odoo_field', k)
                if odoo_field and odoo_field != k:
                    value = partner_vals.pop(k)
                    partner_vals[odoo_field] = value

            # Convertir campos opcionales en campos de Odoo
            for k, v in optional_fields.items():
                odoo_field = v.get('odoo_field', k)
                if odoo_field and odoo_field != k:
                    value = partner_vals.pop(k)
                    partner_vals[odoo_field] = value

            # Manejar tipo de persona
            if 'natural_person' in sanitized_data and sanitized_data['natural_person']:
                natural_person = sanitized_data['natural_person']
                if natural_person not in ['F', 'M']:
                    raise werkzeug.exceptions.UnprocessableEntity('Valor no válido para natural_person')
                else:
                    if natural_person == 'F':
                        partner_vals['company_type'] = 'person'
                        partner_vals['is_company'] = False
                    elif natural_person == 'M':
                        partner_vals['company_type'] = 'company'
                        partner_vals['is_company'] = True

            # Manejar estado
            if sanitized_data.get('state'):
                state = request.env['res.country.state'].sudo().search([
                    '|',
                    ('name', '=ilike', sanitized_data['state']),
                    ('code', '=ilike', sanitized_data['state'])
                ], limit=1)
                if not state:
                    raise werkzeug.exceptions.UnprocessableEntity('Estado no encontrado')
                if state:
                    partner_vals['state_id'] = state.id
                    partner_vals['country_id'] = state.country_id.id

            # Manjear tipo de contacto
            if partner_type == 'client':
                partner_vals['x_is_client'] = True
            elif partner_type == 'supplier':
                partner_vals['x_is_supplier'] = True

            # Crear registro
            partner = request.env['res.partner'].sudo().create(partner_vals)
            request.env.cr.commit()

            _logger.info(f'Cliente creado: ID {partner.id}, RFC: {partner.vat}, Ref. SAP: {partner.x_ref_sap}')

            return {
                'id': partner.id,
                'ref': partner.x_ref_sap,
                'name': partner.name,
                'rfc': partner.vat,
            }

        except werkzeug.exceptions.HTTPException:
            # Re-raise werkzeug exceptions (ya tienen status code correcto)
            request.env.cr.rollback()
            raise

        except (ValidationError, UserError) as e:
            request.env.cr.rollback()
            _logger.warning(f'Error de validación: {str(e)}')
            raise werkzeug.exceptions.BadRequest(str(e))

        except Exception as e:
            request.env.cr.rollback()
            _logger.error(f'Error al crear el registro: {str(e)}', exc_info=True)
            raise werkzeug.exceptions.InternalServerError('Error interno del servidor')

    # @http.route('/api/v1/cliente/<int:partner_id>', type='json', auth='user', methods=['GET'], csrf=False)
    # def get_cliente(self, partner_id, **kwargs):
    #     """Endpoint para obtener un cliente por ID"""
    #     try:
    #         partner = request.env['res.partner'].sudo().browse(partner_id)

    #         if not partner.exists():
    #             raise werkzeug.exceptions.NotFound('Cliente no encontrado')

    #         # Retornar dict directo
    #         return {
    #             'id': partner.id,
    #             'name': partner.name,
    #             'vat': partner.vat,
    #             'company_type': partner.company_type,
    #             'street': partner.street,
    #             'street2': partner.street2,
    #             'street_number': partner.street_number,
    #             'city': partner.city,
    #             'state_id': partner.state_id.name if partner.state_id else None,
    #             'phone': partner.phone,
    #             'mobile': partner.mobile,
    #             'email': partner.email,
    #             'l10n_mx_edi_fiscal_regime': partner.l10n_mx_edi_fiscal_regime,
    #             'l10n_mx_edi_curp': partner.l10n_mx_edi_curp,
    #             'ref': partner.ref,
    #         }

    #     except werkzeug.exceptions.HTTPException:
    #         raise

    #     except Exception as e:
    #         _logger.error(f'Error al obtener cliente: {str(e)}', exc_info=True)
    #         raise werkzeug.exceptions.InternalServerError('Error interno del servidor')
