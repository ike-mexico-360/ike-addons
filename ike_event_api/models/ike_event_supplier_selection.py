# -*- coding: utf-8 -*-

import time
import json
import logging
import requests
import threading

from odoo import models, fields, api, SUPERUSER_ID
from odoo.modules.registry import Registry

_logger = logging.getLogger(__name__)


class IkeEventSupplierSelection(models.Model):
    _inherit = 'ike.event.supplier'

    # Mapeo de valors para el tipo de búsqueda, Odoo -> iké
    SEARCH_TYPE_MAP = {
        "electronic": {"code": 1, "name": "GEO"},
        "publication": {"code": 2, "name": "PUB"},
        "manual": {"code": 3, "name": "MAN"},
        "manual_manual": {"code": 3, "name": "MAN"},
    }

    # Mapeo de subservicios equivalencias Odoo -> iké
    SUB_SERVICE_REF_MAP = {
        "town_truck": {
            "id": "f2c193e7-8517-4c16-a5e3-deb0944fc78b",
            "code": 211,
            "description": "Arrastre de grúa"
        },
        "battery_jump": {
            "id": "4bf0fbe9-dc04-4f1a-b1c5-832379b24542",
            "code": 212,
            "description": "Paso de corriente"
        },
        "tire_change": {
            "id": "67fc3526-57a1-433e-ae6f-96363f77289d",
            "code": 213,
            "description": "Cambio de llanta"
        },
        "fuel_supply": {
            "id": "0442653b-e0cf-4860-a110-97c0a62dbeb5",
            "code": 214,
            "description": "Suministro de gasolina"
        },
    }

    # === OVERRIDE ACTIONS === #
    def action_notify(self)->list[int]:
        """OVERRIDE: send unknown? notification"""
        # SUPER
        result = super().action_notify()
        # Async Notification
        if not self._is_db_neutralized():
            self_filtered = self.filtered(
                lambda x: x.state == 'notified'
                and x.notification_date
                and x.event_id.service_id.x_ref == 'vial'
                and x.event_id.sub_service_id.default_code in self.SUB_SERVICE_REF_MAP.keys()
                and x.supplier_id.x_has_external_notification
                and x.truck_id.x_vehicle_ref
            )
            if self_filtered:
                @self.env.cr.postcommit.add
                def send_notifications_with_new_cursor():
                    threading.Thread(
                        target=self._async_send_notification,
                        args=(self.env.cr.dbname, self_filtered.ids, 'send_external_notification'),
                        # args=(self.env.cr.dbname, self_filtered.ids, '_testing_async_method', 'send_external_notification'),  # ? TESTING
                        daemon=True,
                    ).start()
        return result

    def action_notify_operator(self)->list[int]:
        """OVERRIDE: send operator notification"""
        self_filtered = self.filtered(lambda x: x.state == 'accepted')
        if not self_filtered:
            return []
        # Async Notification
        if not self._is_db_neutralized():
            threading.Thread(
                target=self._async_send_notification,
                args=(self.env.cr.dbname, self_filtered.ids, 'send_operator_notification'),
                # args=(self.env.cr.dbname, self_filtered.ids, '_testing_async_method', 'send_operator_notification'),  # ? TESTING
                daemon=True,
            ).start()
        # SUPER
        result = super().action_notify_operator()
        return result

    def action_accept(self)->list[int]:
        """OVERRIDE: send user notification"""
        result = super().action_accept()
        selected_suppliers = self.filtered(lambda x: x.selected)
        # FixMe: check len == 1 ?
        if len(selected_suppliers) == 1 and not self._is_db_neutralized():
            @self.env.cr.postcommit.add
            def send_notifications_with_new_cursor():
                threading.Thread(
                    target=self._async_send_notification,
                    args=(self.env.cr.dbname, selected_suppliers.ids, 'send_accept_notification'),
                    # args=(self.env.cr.dbname, selected_suppliers.ids, '_testing_async_method', 'send_accept_notification'),  # ? TEST
                    daemon=True
                ).start()
        return result

    # def action_reject(self):
    # def action_timeout(self):
    # def action_expire(self):

    def action_cancel(self, cancel_reason_id: int, reason_text=None):
        """OVERRIDE: send user notification"""
        # Filtrar los operadores a notificar cancelación
        self_filtered = self.filtered(lambda x: x.state in ['accepted', 'assigned'] and not x.stage_ref == 'finalized')
        self_filtered_app = self_filtered.filtered(lambda x: x.supplier_id.x_has_external_notification is False)
        self_filtered_external = self_filtered.filtered(lambda x: x.supplier_id.x_has_external_notification is True)

        result = super().action_supplier_cancel(cancel_reason_id, reason_text)

        # Lógica para notificar la cancelación a la app
        if self_filtered_app and not self._is_db_neutralized():
            try:
                @self.env.cr.postcommit.add
                def send_notifications_with_new_cursor():
                    threading.Thread(
                        target=self._async_send_notification,
                        args=(self.env.cr.dbname, self_filtered_app.ids, 'send_cancel_notification', 'internal'),
                        # args=(self.env.cr.dbname, self_filtered.ids, '_testing_async_method', 'send_cancel_notification'),  # ? TEST
                        daemon=True,
                    ).start()
            except Exception as e:
                _logger.error(f"Error sending global notification to app: {str(e)}")

        if self_filtered_external and not self._is_db_neutralized():
            try:
                @self.env.cr.postcommit.add
                def send_notifications_with_new_cursor_external():
                    threading.Thread(
                        target=self._async_send_notification,
                        args=(
                            self.env.cr.dbname,
                            self_filtered_external.ids,
                            'send_cancel_notification_to_external',
                            cancel_reason_id,
                            reason_text,
                            'external'
                        ),
                        daemon=True,
                    ).start()
            except Exception as e:
                _logger.error(f"Error sending cancel notification to external: {str(e)}")

        return result

    def action_event_cancel(self, cancel_reason_id: int, reason_text=None):
        """OVERRIDE: send user notification"""
        # Filtrar los operadores a notificar cancelación
        self_filtered = self.filtered(lambda x: x.state in ['accepted', 'assigned'] and not x.stage_ref == 'finalized')
        self_filtered_app = self_filtered.filtered(lambda x: x.supplier_id.x_has_external_notification is False)
        self_filtered_external = self_filtered.filtered(lambda x: x.supplier_id.x_has_external_notification is True)

        result = super().action_supplier_cancel(cancel_reason_id, reason_text)

        if self_filtered_app and not self._is_db_neutralized():
            try:
                @self.env.cr.postcommit.add
                def send_notifications_with_new_cursor():
                    threading.Thread(
                        target=self._async_send_notification,
                        args=(self.env.cr.dbname, self_filtered_app.ids, 'send_cancel_notification', 'event'),
                        # args=(self.env.cr.dbname, self_filtered.ids, '_testing_async_method', 'send_cancel_notification'),  # ? TEST
                        daemon=True,
                    ).start()
            except Exception as e:
                _logger.error(f"Error sending global notification to app: {str(e)}")

            if self_filtered_external and not self._is_db_neutralized():
                try:
                    @self.env.cr.postcommit.add
                    def send_notifications_with_new_cursor_external():
                        threading.Thread(
                            target=self._async_send_notification,
                            args=(
                                self.env.cr.dbname,
                                self_filtered_external.ids,
                                'send_cancel_notification_to_external',
                                cancel_reason_id,
                                reason_text,
                                'external'
                            ),
                            daemon=True,
                        ).start()
                except Exception as e:
                    _logger.error(f"Error sending cancel notification to external: {str(e)}")

        return result

    def action_supplier_cancel(self, cancel_reason_id: int, reason_text=None):
        """OVERRIDE: send user notification"""
        self_filtered = self.filtered(lambda x: x.state in ['accepted', 'assigned'] and not x.stage_ref == 'finalized')
        result = super().action_supplier_cancel(cancel_reason_id, reason_text)

        if not self._is_db_neutralized():
            @self.env.cr.postcommit.add
            def send_notifications_with_new_cursor():
                threading.Thread(
                    target=self._async_send_notification,
                    args=(self.env.cr.dbname, self_filtered.ids, 'send_cancel_notification', 'portal'),
                    # args=(self.env.cr.dbname, self_filtered.ids, '_testing_async_method', 'send_cancel_notification'),  # ? TEST
                    daemon=True,
                ).start()

        return result

    # === ASYNC EXECUTION === #
    def _async_send_notification(self, db_name, record_ids, action_name, *args):
        """Thread to send notification"""
        db_registry = Registry(db_name)
        with db_registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})

            records = env['ike.event.supplier'].browse(record_ids).sudo()
            # print(records.ids, records.name)
            method = getattr(records, action_name, None)
            if callable(method):
                method(*args)

    def _testing_async_method(self, real_action_name: str):
        time.sleep(10)
        print("ASYNC TEST DONE", real_action_name)

    # === SEND EXTERNAL NOTIFICATIONS === #
    def send_external_notification(self):
        url = self.env['ir.config_parameter'].sudo().get_param('ike_event.url.send_external_supplier')
        if not url:
            _logger.warning("No se ha configurado la URL de notificación a proveedores externos")
            return

        # ? ToImprove: Bulk/Batch send improve
        headers = {"Content-Type": "application/json"}
        notification_responses = []
        for rec in self:
            try:
                body = rec._prepare_body_for_external_notification()
                # _logger.warning(f"Sending external notification: {body}")
                external_response = requests.post(
                    str(url),
                    headers=headers,
                    json=body,
                )
                if external_response:
                    notification_responses.append(external_response.json())
            except Exception as e:
                _logger.error(f"Sending external notification Error: {str(e)}")
                return None
        # for response in notification_responses:
        #     _logger.info(f"External notification: {response}")

    def send_operator_notification(self):
        # Supplier Notification
        supplier_responses = []
        IrConfig = self.env['ir.config_parameter'].sudo()
        notification_url = IrConfig.get_param('ike_event.app.url.notification')
        if notification_url:
            # Request
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Python-IoT-Test/1.0",
            }

            for rec in self:
                if rec.supplier_id.x_has_external_notification:
                    continue
                if rec.truck_id.driver_id and rec.supplier_id.x_has_portal is True:
                    try:
                        notification_response = requests.post(
                            str(notification_url),
                            headers=headers,
                            params={
                                "user_id": str(rec.truck_id.driver_id.user_ids[0].id),
                                "vehicle_id": str(rec.truck_id.x_vehicle_ref),
                            },
                            json={
                                "service_id": str(rec.event_id.id),
                                "ca_id": str(rec.truck_id.x_center_id.id),
                                "lng": str(rec.event_id.location_latitude),
                                "lat": str(rec.event_id.location_longitude),
                                "dst_lng": str(rec.event_id.destination_latitude),
                                "dst_lat": str(rec.event_id.destination_longitude),
                                "control": "1",  # mesa de control
                                "assignation_type": str(rec.assignation_type),
                                "estatus": str(rec.state),
                                "event_supplier_id": str(rec.id),
                                "user_code": str(rec.event_id.user_code),
                                "DB": self.env.cr.dbname,  # Base de datos para distinguir de donde provienen las notificaciones
                            },
                        )
                        if notification_response:
                            response_json = notification_response.json()
                            supplier_responses.append(response_json)
                            topic = response_json.get("topic", False)
                            if topic and topic == f"vehiculos/{rec.truck_id.driver_id.user_ids[0].id}/{rec.truck_id.x_vehicle_ref}":
                                # rec.notification_sent_to_app = True
                                query = """
                                    UPDATE ike_event_supplier
                                    SET notification_sent_to_app = true
                                    WHERE id = %
                                """
                                params = (rec.id)
                                self.env.cr.execute(query, params)
                    except Exception as e:
                        _logger.error(f"Error en notificación: {str(e)}")

            # for response in supplier_responses:
            #     _logger.info(f"Notified by portal: {response}")
            # En el log debemos ver algo como:
            # {
            #     'success': True,
            #     'message': 'Event published to IoT Core',
            #     'topic': 'vehiculos/2/27',
            #     'method': 'default_endpoint',
            #     'request_id': '71e29af8-24a5-4fec-b821-a2563b8e2473'
            # }
        else:
            _logger.warning("No se ha configurado la URL para las notificaciones")

        # Route Notification
        tracking_responses = []
        route_tracking_url = IrConfig.get_param('ike_event_api.url.send_route')
        if route_tracking_url:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Python-IoT-Test/1.0",
            }
            for rec in self:
                if not rec.route:
                    continue

                origin = {
                    "lat": rec.event_id.location_latitude,
                    "lng": rec.event_id.location_longitude,
                    "label": rec.event_id.location_label,
                }
                destination = {
                    "lat": rec.event_id.destination_latitude,
                    "lng": rec.event_id.destination_longitude,
                    "label": rec.event_id.destination_label,
                }

                # Si route_to_user es string
                if rec.route:
                    if isinstance(rec.route, str):
                        route_to_user = json.loads(rec.route)
                    else:
                        route_to_user = rec.route  # Ya es lista
                else:
                    route_to_user = []
                # Si route_to_destination es string
                if rec.event_id.destination_route:
                    if isinstance(rec.event_id.destination_route, str):
                        route_to_destination = json.loads(rec.event_id.destination_route)
                    else:
                        route_to_destination = rec.event_id.destination_route  # Ya es lista
                else:
                    route_to_destination = []

                try:
                    if route_to_user is None:
                        route_to_user = []
                    if route_to_destination is None:
                        route_to_destination = []
                    dest_lat = destination.get('lat', False)
                    dest_lng = destination.get('lng', False)
                    if not dest_lat and not dest_lng:
                        destination = origin
                        origin = {
                            "lat": False,
                            "lng": False,
                            "label": False,
                        }
                    routes = [route_to_user, route_to_destination]
                    json_data = {
                        "serviceId": str(rec.event_id.id),
                        "vehicleId": str(rec.event_id.id),
                        "origin": origin,
                        "destination": destination,
                        "routes": routes,
                        "DB": self.env.cr.dbname,  # Base de datos para distinguir el ambiente de donde se envía
                    }
                    tracking_response = requests.post(
                        str(route_tracking_url),
                        headers=headers,
                        json=json_data,
                    )
                    if tracking_response:
                        tracking_responses.append(tracking_response.json())
                except Exception as e:
                    _logger.error(f"Error en ruta: {str(e)}")
            # for response in tracking_responses:
            #     _logger.info(f"Tracking route: {response}")
        else:
            _logger.warning("No se ha configurado la URL para el envío de rutas")

    def send_accept_notification(self):
        try:
            time.sleep(30)
            wp_access_token = self.x_get_whatsapp_token()

            if wp_access_token:
                # FixMe: self[0]?
                supplier = self[0]
                decrypt_encrypt_utility_sudo = self.env['custom.encryption.utility'].sudo()
                phone_number = decrypt_encrypt_utility_sudo.decrypt_aes256(supplier.event_id.user_id.phone or '')

                parameter = f"de su servicio ha iniciado, el vehículo asignado es {supplier.truck_id.name},"\
                    f" con matrícula {supplier.truck_id.license_plate}. Deberá proporcionar el siguiente"\
                    f" código #{supplier.event_id.user_code} a"
                successfully_sent = supplier.x_send_whatsapp_template(
                    access_token=wp_access_token,
                    event_id=str(supplier.event_id.id),
                    template=71,  # Código verificador
                    phone_number=phone_number,
                    parameter=parameter,
                )
                if successfully_sent:
                    _logger.info(f"WP Send user code: {parameter}")
                else:
                    _logger.error("WP Send user code: Error al enviar el código de usuario")
            else:
                _logger.error("WP Send user code: Error al obtener el token de acceso")
        except Exception as e:
            _logger.error(f"WP Send user code: Error al enviar el código de usuario: {str(e)}")

    def send_cancel_notification(self, origin):
        app_notification_url =\
            self.env['ir.config_parameter'].sudo().get_param('ike_event.app.url.global_notification')
        if not app_notification_url:
            _logger.warning("No se ha configurado la URL de notificación global a la app")
            return
        app_notification_url = str(app_notification_url)

        notification_responses = []
        headers = {"Content-Type": "application/json"}
        for rec in self:
            try:
                body = {
                    "vehicleId": str(rec.truck_id.x_vehicle_ref),
                    "userId": None,
                    "payload": {
                        "type": "TRAVEL_CANCELATION",
                        "details": {
                            "serviceId": str(rec.event_id.id),
                        }
                    }
                }
                response = requests.post(
                    app_notification_url,
                    headers=headers,
                    json=body,
                )
                notification_responses.append(response.json)
            except Exception as e:
                _logger.error(f"Error sending notification: {str(e)}")
        # for response in notification_responses:
        #     if 'ok' in response:
        #         _logger.info(f"Notification sent successfully ({origin}): {response}")
        #     else:
        #         _logger.warning(f"Error sending notification ({origin}): {response}")

    def send_cancel_notification_to_external(self, str, cancel_reason_id, reason_text, origin: str = 'internal'):
        external_supplier_notification_url =\
            self.env['ir.config_parameter'].sudo().get_param('ike_event.app.url.cancel_external_notification')
        if not external_supplier_notification_url:
            _logger.warning("No se ha configurado la URL de notificación a proveedores externos")
            return
        external_supplier_notification_url = str(external_supplier_notification_url)
        for supplier in self:
            headers = {"Content-Type": "application/json"}
            body = {
                "folio": str(supplier.event_id.id),
                "craneId": str(supplier.truck_id.x_vehicle_ref),
                "motivo": cancel_reason_id,
                "observaciones": reason_text if reason_text else ""
            }
            _logger.warning(f"Sending external notification: {body}")
            external_notification_response = requests.post(
                external_supplier_notification_url,
                headers=headers,
                json=body,
            )
            try:
                notification_data = external_notification_response.json()
                if notification_data.get('error', True):
                    _logger.info(f"External notification sent successfully ({supplier.event_id.id}/{supplier.truck_id.x_vehicle_ref}): {notification_data}")
                else:
                    _logger.warning(f"Error sending external notification ({supplier.event_id.id}/{supplier.truck_id.x_vehicle_ref}): {notification_data}")
            except Exception as e:
                _logger.warning(f"Error sending external notification ({supplier.event_id.id}/{supplier.truck_id.x_vehicle_ref}): {notification_data.text}")

    # === PRIVATE METHODS === #
    def _is_db_neutralized(self):
        # return self.env['ir.config_parameter'].sudo().get_param('database.is_neutralized')
        return False

    def _prepare_body_for_external_notification(self):
        self.ensure_one()

        # Mapeo de estados Odoo -> iké
        def get_status(ref):
            if ref in ('preparing', 'assigned', 'on_route', 'arrived', 'contacted', 'on_route_2', 'arrived_2'):
                return {'code': 1, 'name': 'Abierto'}
            elif ref == 'finalized':
                return {'code': 2, 'name': 'Cerrado'}
            return {}

        service_model_id = self.event_id.get_service_model()

        # Para subsevicios que no tienen todos los campos necesarios para notificar... aplicar read para obtener
        # solo los existentes necesarios
        sub_service_model_id = self.event_id.get_sub_service_model()
        sub_service_valid_fields = list(sub_service_model_id._fields.keys())
        needed_fields = [
            'destination_zip_code',
            'state_id',
            'municipality_id',
            'colony',
            'street',
            'street_number',
            'street2',
            'street_ref',
            'destination_latitude',
            'destination_longitude'
        ]
        fields_to_read = [f for f in needed_fields if f in sub_service_valid_fields]
        subservice_data = sub_service_model_id.read(fields_to_read)
        subservice_data = subservice_data[0]

        range_high = False
        if service_model_id.vehicle_category_id:  # type: ignore
            range_high = bool(service_model_id.vehicle_category_id.name.strip().lower().replace(' ', '') == 'altagama')  # type: ignore

        survey_input_data = self.event_id.get_survey_input_data()
        decrypt_utility = self.env['custom.encryption.utility'].sudo()

        body = {
            "id": str(self.event_id.id),
            "user": decrypt_utility.decrypt_aes256(self.event_id.user_id.name or ''),
            "placeEvent": self.event_id.event_type_id.name or '',
            "car": {
                "yearCar": service_model_id.vehicle_year or '',  # type: ignore
                "typeCar": service_model_id.vehicle_model or '',  # type: ignore
                "brandCar": service_model_id.vehicle_brand or '',  # type: ignore
                "colorCar": service_model_id.vehicle_color or '',  # type: ignore
                "platesCar": service_model_id.vehicle_plate or '',  # type: ignore
                "rangehigh": range_high,
                "rangetype": service_model_id.vehicle_category_id.name or '',  # type: ignore
            },
            # Servicio se envía estático, solo se notifica en Asistencia vial
            "service": {
                "code": "1",
                "description": "Asistencia Vial",
                "id": "81485957-cff2-4db0-8722-12c666d23b65"
            },
            "subservice": self.SUB_SERVICE_REF_MAP.get(self.event_id.sub_service_id.default_code, {}),
            "origin": {
                "postalCode": service_model_id.location_zip_code or '',  # type: ignore
                "state": service_model_id.state_id.name or '',  # type: ignore
                "municipality": service_model_id.municipality_id.name or '',  # type: ignore
                "neighborhood": service_model_id.colony or '',  # type: ignore
                "street": f"{service_model_id.street} {service_model_id.street_number}" or '',  # type: ignore
                "betweenStreets": service_model_id.street2 or '',  # type: ignore
                "visualReference": service_model_id.street_ref or '',  # type: ignore
                "latitude": service_model_id.location_latitude or '',  # type: ignore
                "longitude": service_model_id.location_longitude or '',  # type: ignore
            },
            "destino": {
                "postalCode": subservice_data.get('destination_zip_code', ''),
                "state": subservice_data['state_id'][1] if subservice_data.get('state_id', False) else '',
                "municipality": subservice_data['municipality_id'][1] if subservice_data.get('municipality_id', False) else '',
                "neighborhood": subservice_data.get('colony', ''),
                "street": (
                    f"{subservice_data['street']} {subservice_data['street_number']}"
                    if subservice_data.get('street', False) and subservice_data.get('street_number', False)
                    else ''
                ),
                "betweenStreets": subservice_data.get('street2', ''),
                "visualReference": subservice_data.get('street_ref', ''),
                "latitude": subservice_data.get('destination_latitude', ''),
                "longitude": subservice_data.get('destination_longitude', ''),
            },
            "typeAssignment": {
                "code": self.SEARCH_TYPE_MAP.get(self.assignation_type, {}).get('code'),
                "description": self.SEARCH_TYPE_MAP.get(self.assignation_type, {}).get('name'),
                "id": str(self.truck_id.x_vehicle_ref) if self.truck_id.x_vehicle_ref else '',
            },
            "serviceDetails": survey_input_data,
        }

        # handle status
        status = get_status(self.stage_id.ref)
        body.update({
            "status": {
                "code": status['code'],
                "description": status['name'],
            }
        })

        return body

    # === AUX METHODS === #
    def x_get_whatsapp_token(self):
        # ToDo: Implementar expiración de token
        # ToDo: Mover a custom_nu
        allow_send_whatsapp = bool(self.env['ir.config_parameter'].sudo().get_param('events.allow_send_whatsapp'))
        if not allow_send_whatsapp:
            return False

        access_token = False
        login_url = self.env['ir.config_parameter'].sudo().get_param('ike_event_api.wp_service.login_url')
        if not login_url:
            return False

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Python-IoT-Test/1.0",
        }
        userName = self.env['ir.config_parameter'].sudo().get_param('ike_event_api.wp_service.login.user')
        password = self.env['ir.config_parameter'].sudo().get_param('ike_event_api.wp_service.login.pass')
        login_body = {
            "userName": userName,
            "password": password
        }
        if not userName or not password:
            _logger.error("WP Token: Error al obtener credenciales de usuario")

        try:
            login_response = requests.post(str(login_url), headers=headers, json=login_body)
            data_login = login_response.json()
            access_token = data_login.get('data', {}).get('accessToken', False)
        except Exception as e:
            _logger.error(f"WP Token: Error al enviar petición: {str(e)}")
        return access_token

    def x_send_whatsapp_template(
        self,
        access_token: str,
        event_id: str,
        template: int,
        phone_number: str,
        parameter=None
    ):
        # ToDo: Mover a custom_nu
        allow_send_whatsapp = bool(self.env['ir.config_parameter'].sudo().get_param('events.allow_send_whatsapp'))
        if not allow_send_whatsapp:
            return False

        template_url = self.env['ir.config_parameter'].sudo().get_param('ike_event_api.wp_service.template_url')
        if not template_url:
            return False

        if not access_token:
            _logger.warning("No se ha configurado el token de acceso para el whatsapp")
            return False

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Python-IoT-Test/1.0",
            "Authorization": access_token,
        }
        body = {
            "identifier": {
                "appId": 16,
                "tenants": "adff7f6a-e97d-11eb-9a03-0242ac130003",
                "reference": event_id,
            },
            "petition": {
                "phoneNumber": phone_number,
                "templateId": template,
            }
        }
        if parameter:
            body['petition']['templateParameters'] = [{"parameter": parameter}]
        # _logger.warning(f"WP User code: headers: {headers}")
        _logger.warning(f"WP Template {template}: body: {body}")
        try:
            response = requests.post(str(template_url), headers=headers, json=body)
            response_json = response.json()
            _logger.info(f"WP Template {template}: response: {response_json}")
            return True
        except Exception as e:
            _logger.error(f"WP Template {template}: Error enviando petición: {str(e)}")
            return False


class IkeEventSupplierElapsedTime(models.Model):
    _name = 'ike.event.supplier.elapsed_time'
    _description = 'Event Supplier Elapsed Time'

    event_id = fields.Many2one('ike.event', ondelete='cascade', required=True)
    vehicle_id = fields.Many2one('fleet.vehicle', required=True)
    stage_id = fields.Many2one('ike.service.stage', required=True)
    app_timestamp = fields.Datetime(required=True)
    elapsed_seconds = fields.Integer(required=True)
    latitude = fields.Char()
    longitude = fields.Char()
