# -*- coding: utf-8 -*-

import json
import logging
import requests
from odoo import models, fields

_logger = logging.getLogger(__name__)


class IkeEventSupplierSelection(models.Model):
    _inherit = 'ike.event.supplier'

    SEARCH_TYPE_MAP = {
        'electronic': {'code': 1, 'name': 'GEO'},
        'publication': {'code': 2, 'name': 'PUB'},
        'manual': {'code': 3, 'name': 'MAN'},
        'manual_manual': {'code': 3, 'name': 'MAN'},
    }
    # Necesario para mapear los sub_servicios antes de entrar a la lógica de la notificaciíon y filtrar
    SUB_SERVICE_REF_MAP = {
        'town_truck': {'code': 211, 'name': 'Arrastre de grúa'},
        'fuel_supply': {'code': 213, 'name': 'Suministro de gasolina'},
        'battery_charge': {'code': 214, 'name': 'Paso de corriente'},
        'tire_change': {'code': 215, 'name': 'Cambio de llanta'},
    }

    # === Private methdos === #
    def _is_db_neutralized(self):
        return self.env['ir.config_parameter'].sudo().get_param('database.is_neutralized')

    def _prepare_body_for_external_notification(self):
        def get_status(ref):
            if ref in ('preparing', 'assigned', 'on_route', 'arrived', 'contacted', 'on_route_2', 'arrived_2'):
                return {'code': 1, 'name': 'Abierto'}
            elif ref == 'finalized':
                return {'code': 2, 'name': 'Cerrado'}
            return {}

        service_id = self.env[self.event_id.service_res_model].browse(self.event_id.service_res_id)
        sub_service_id = self.env[self.event_id.sub_service_res_model].browse(self.event_id.sub_service_res_id)
        rangehigh = False
        if service_id.vehicle_category_id:
            rangehigh = bool(service_id.vehicle_category_id.name.strip().lower().replace(' ', '') == 'altagama')

        body = {
            "id": str(self.event_id.id),
            "car": {
                "yearCar": service_id.vehicle_year or '',
                "typeCar": service_id.vehicle_model or '',
                "brandCar": service_id.vehicle_brand or '',
                "colorCar": service_id.vehicle_color or '',
                "platesCar": service_id.vehicle_plate or '',
                "rangehigh": rangehigh,
                "rangetype": service_id.vehicle_category_id.name or ''
            },
            "service": {
                "code": "1",  # ToDo: queda fijo, se cambiará al definirse el origen
                "description": "Asistencia Vial",  # ToDo: queda fijo, se cambiará al definirse el origen
                "id": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"  # ToDo: queda fijo, se cambiará al definirse el origen
            },
            "subservice": {
                "id": "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                "code": self.SUB_SERVICE_REF_MAP.get(self.event_id.sub_service_id.default_code)['code'],
                "description": self.SUB_SERVICE_REF_MAP.get(self.event_id.sub_service_id.default_code)['name']
            },
            "origin": {
                "postalCode": service_id.location_zip_code or '',
                "state": service_id.state_id.name or '',
                "municipality": service_id.municipality_id.name or '',
                "neighborhood": service_id.colony or '',
                "street": f"{service_id.street} {service_id.street_number}" or '',
                "betweenStreets": service_id.street2 or '',
                "visualReference": service_id.street_ref or '',
                "latitude": service_id.location_latitude or '',
                "longitude": service_id.location_longitude or '',
            },
            "destino": {
                "postalCode": sub_service_id.destination_zip_code or '',
                "state": sub_service_id.state_id.name or '',
                "municipality": sub_service_id.municipality_id.name or '',
                "neighborhood": sub_service_id.colony or '',
                "street": f"{sub_service_id.street} {sub_service_id.street_number}" or '',
                "betweenStreets": sub_service_id.street2 or '',
                "visualReference": sub_service_id.street_ref or '',
                "latitude": sub_service_id.destination_latitude or '',
                "longitude": sub_service_id.destination_longitude or '',
            },
            # ToDo: Validar que el tipo de asignación sea el mismo para el grupo de vehículos que se enviará en la lista ids
            "typeAssignment": {
                "code": self.SEARCH_TYPE_MAP.get(self.assignation_type)['code'],
                "description": self.SEARCH_TYPE_MAP.get(self.assignation_type)['name'],
                # ToDo: Se enviará un array bajo la clave ids, array de uid's
                # "ids": [str(supplier.truck_id.x_vehicle_ref) for supplier in self]
                "id": str(self.truck_id.x_vehicle_ref) if self.truck_id.x_vehicle_ref else '',
            },
            # ToDo: Mapear con las respuestas de la encuesta
            "serviceDetails": {
                "reasonFailure": {
                    "id": 0,
                    "description": "NU no sabe",
                    "code": 7
                },
                "accompaniesTransfer": {
                    "id": 0,
                    "description": "Nuestro Usuario",
                    "code": 1
                },
                "typeFaul": {
                    "id": 0,
                    "description": "MECANICA",
                    "code": 1
                },
                "peopleVehicle": 1
            },
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

    # === AUXILIAR METHODS === #
    def operator_app_notify(
        self, url: str, user_id: str, vehicle_id: str, service_id: str, ca_id: str, lat: str, lng: str, dst_lat: str,
        dst_lng: str, control: str, assignation_type: str, status: str, event_supplier_id: str, user_code: str,
    ):
        if not url:
            return False
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Python-IoT-Test/1.0",
            },
            params={
                "user_id": user_id,  # operador asignado al vehículo
                "vehicle_id": vehicle_id,  # vehículo
            },
            json={
                "service_id": service_id,  # id del evento
                "ca_id": ca_id,  # centro de atención
                "lng": lng,  # recolección
                "lat": lat,  # recolección
                "dst_lng": dst_lng,  # destino
                "dst_lat": dst_lat,  # destino
                "control": control,  # mesa de control
                "assignation_type": assignation_type,  # Tipo de asignación
                "estatus": status,
                "event_supplier_id": event_supplier_id,  # ID de la linea del modelo ik.event.supplier
                "user_code": user_code,  # Código de usuario
                "DB": self.env.cr.dbname,  # Base de datos para distinguir de donde provienen las notificaciones
            },
        )
        return response.json()

    def send_route_tracking(
        self, url, service_id, vehicle_id, origin, destination, route_to_user=None, route_to_destination=None,
    ):
        if route_to_user is None:
            route_to_user = []
        if route_to_destination is None:
            route_to_destination = []
        if not url:
            return False
        # ToDo: Escenario para sub-servicios de un solo punto, está bien así?
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
            "serviceId": service_id,  # id del evento
            "vehicleId": vehicle_id,
            "origin": origin,
            "destination": destination,
            "routes": routes,
            "DB": self.env.cr.dbname,  # Base de datos para distinguir el ambiente de donde se envía
        }
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Python-IoT-Test/1.0",
            },
            json=json_data,
        )
        _logger.info(f"Sending route payload: {json_data}")
        return response.json()

    def notify_external_supplier(self, url: str):
        if not url:
            return False

        # ToDo: IMP: Agrupar por evento para enviar los batchs
        headers = {"Content-Type": "application/json"}
        body = self._prepare_body_for_external_notification()
        external_response = requests.post(
            url,
            headers=headers,
            json=body,
        )
        return external_response.json()

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
            login_response = requests.post(login_url, headers=headers, json=login_body)
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
            response = requests.post(template_url, headers=headers, json=body)
            response_json = response.json()
            _logger.info(f"WP Template {template}: response: {response_json}")
            return True
        except Exception as e:
            _logger.error(f"WP Template {template}: Error enviando petición: {str(e)}")
            return False

    # === Override methods === #
    def action_notify_cancelation_to_app(self, url: str, origin: str = 'internal'):
        for rec in self:
            headers = {"Content-Type": "application/json"}
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
            service_notification_response = requests.post(
                url,
                headers=headers,
                json=body,
            )
            service_data = service_notification_response.json()
            if 'ok' in service_data:
                _logger.info(f"Notification sent successfully ({origin}): {service_data}")
            else:
                _logger.warning(f"Error sending notification ({origin}): {service_data}")

    def action_notify(self):
        # Override
        res = super().action_notify()

        url = self.env['ir.config_parameter'].sudo().get_param('ike_event.url.send_external_supplier')
        if not url:
            _logger.warning("No se ha configurado la URL de notificación a proveedores externos")
            return res

        self_filtered = self.filtered(
            lambda x: x.state == 'notified'  # Notiticados
            and x.notification_date  # Con fecha de notificación
            and x.event_id.service_id.x_ref == 'vial'  # Tipo vial
            and x.event_id.sub_service_id.default_code in self.SUB_SERVICE_REF_MAP.keys()  # Que sea de los subservicios mapeados
            and x.supplier_id.x_has_external_notification  # Que tenga notificación externa
            and x.truck_id.x_vehicle_ref  # Que tenga uid el vehiculo
        )
        # ToDo: Enviar por batch
        for rec in self_filtered:
            response = False
            try:
                response = rec.notify_external_supplier(url)
            except Exception as e:
                _logger.error(f"Error al notificar a proveedor: {str(e)}")
            _logger.info(f"Notified external supplier {rec.event_id.id}/{rec.truck_id.x_vehicle_ref}: {response}")
            # response => 'success': True or False
        return res

    def action_notify_operator(self):
        # Realizamos el proces antes del super, ya que después del super, el filtrado de self_filtered se complicaría,
        # ya que se le cambia el valor al estado

        self_filtered = self.filtered(lambda x: x.state == 'accepted' and not x.notification_sent_to_app)

        supplier_responses = []
        IrConfig = self.env['ir.config_parameter'].sudo()
        url_notifications = IrConfig.get_param('ike_event.app.url.notification')
        if not url_notifications:
            _logger.warning("No se ha configurado la URL para las notificaciones")

        if url_notifications and not self._is_db_neutralized():  # No ejecutar si está neutralizado
            for s in self_filtered:
                if s.truck_id.driver_id and s.supplier_id.x_has_portal is True:

                    # Hack, saltar si el proveedor maneja notificación externa
                    if s.supplier_id.x_has_external_notification:
                        continue

                    try:
                        response = self.operator_app_notify(
                            url=url_notifications,
                            user_id=str(s.truck_id.driver_id.user_ids[0].id),
                            vehicle_id=str(s.truck_id.x_vehicle_ref),
                            service_id=str(s.event_id.id),
                            ca_id=str(s.truck_id.x_center_id.id),
                            lat=str(s.event_id.location_latitude),
                            lng=str(s.event_id.location_longitude),
                            dst_lat=str(s.event_id.destination_latitude),
                            dst_lng=str(s.event_id.destination_longitude),
                            control="1",  # Mandar 1 cuando tiene mesa de control
                            assignation_type=str(s.assignation_type),
                            status=str(s.state),  # ToDo: Es este estado?
                            event_supplier_id=str(s.id),  # ID de la linea del modelo ik.event.supplier
                            user_code=str(s.event_id.user_code),  # Código de usuario
                        )
                        supplier_responses.append(response)
                        topic = response.get("topic", False)
                        if topic and topic == f"vehiculos/{s.truck_id.driver_id.user_ids[0].id}/{s.truck_id.x_vehicle_ref}":
                            # Marcar la linea como notificada
                            s.notification_sent_to_app = True
                    except Exception as e:
                        _logger.error(f"Error en notificación: {str(e)}")
            for response in supplier_responses:
                _logger.info(f"Notified by portal: {response}")
                # En el log debemos ver algo como:
                # {
                #     'success': True,
                #     'message': 'Event published to IoT Core',
                #     'topic': 'vehiculos/2/27',
                #     'method': 'default_endpoint',
                #     'request_id': '71e29af8-24a5-4fec-b821-a2563b8e2473'
                # }

        tracking_responses = []
        url_route_tracking = IrConfig.get_param('ike_event_api.url.send_route')
        if not url_route_tracking:
            _logger.warning("No se ha configurado la URL para el envío de rutas")
        if url_route_tracking and not self._is_db_neutralized():  # No ejecutar si está neutralizado
            for s in self_filtered:
                if not s.route:
                    continue
                # if s.truck_id.driver_id:
                _logger.info(f"Preparando ruta para {s.truck_id.license_plate}")
                origin = {
                    "lat": s.event_id.location_latitude,
                    "lng": s.event_id.location_longitude,
                    "label": s.event_id.location_label,
                }
                destination = {
                    "lat": s.event_id.destination_latitude,
                    "lng": s.event_id.destination_longitude,
                    "label": s.event_id.destination_label,
                }

                # Si route_to_user es string
                if s.route:
                    if isinstance(s.route, str):
                        route_to_user = json.loads(s.route)
                    else:
                        route_to_user = s.route  # Ya es lista
                else:
                    route_to_user = []
                # Si route_to_destination es string
                if s.event_id.destination_route:
                    if isinstance(s.event_id.destination_route, str):
                        route_to_destination = json.loads(s.event_id.destination_route)
                    else:
                        route_to_destination = s.event_id.destination_route  # Ya es lista
                else:
                    route_to_destination = []

                try:
                    tracking_response = self.send_route_tracking(
                        url=url_route_tracking,
                        service_id=str(s.event_id.id),
                        vehicle_id=str(s.truck_id.x_vehicle_ref),
                        origin=origin,
                        destination=destination,
                        route_to_user=route_to_user,
                        route_to_destination=route_to_destination,
                    )
                    tracking_responses.append(tracking_response)
                except Exception as e:
                    _logger.error(f"Error en ruta: {str(e)}")
            for response in tracking_responses:
                _logger.info(f"Tracking route: {response}")

        return super().action_notify_operator()

    def action_accept(self):
        res = super().action_accept()
        # IMP - Send user code to Whatsapp
        # -- Al asignar proveedor, se notifica por whatsapp

        # Enviar solo 1 vez, si es el primero que se acepta
        selected_suppliers = self.filtered(lambda x: x.selected)
        if not selected_suppliers:
            try:
                wp_access_token = self.x_get_whatsapp_token()

                if not wp_access_token:
                    _logger.error("WP Send user code: Error al obtener el token de acceso")

                if wp_access_token:
                    supplier = self[0]
                    decrypt_encrypt_utility_sudo = self.env['custom.encryption.utility'].sudo()
                    phone_number = decrypt_encrypt_utility_sudo.decrypt_aes256(supplier.event_id.user_id.phone or '')

                    parameter = f"de su servicio ha iniciado, el vehículo asignado es {supplier.truck_id.name},"\
                        f" con matrícula {supplier.truck_id.license_plate}. Deberá proporcionar el siguiente"\
                        f" código #{supplier.event_id.user_code} a"
                    successfully_sent = self.x_send_whatsapp_template(
                        access_token=wp_access_token,
                        event_id=str(supplier.event_id.id),
                        template=71,  # CodigoVerificador
                        phone_number=phone_number,
                        parameter=parameter,
                    )
                    if successfully_sent:
                        _logger.info(f"WP Send user code: {parameter}")
                    else:
                        _logger.error("WP Send user code: Error al enviar el código de usuario")
            except Exception as e:
                _logger.error(f"WP Send user code: Error al enviar el código de usuario: {str(e)}")
        return res

    def action_cancel(self, cancel_reason_id: int, reason_text=None):
        # Implement: Notify cancel from internal to app
        global_app_notification_url =\
            self.env['ir.config_parameter'].sudo().get_param('ike_event.app.url.global_notification')
        self_filtered = self.filtered(lambda x: x.state in ['accepted', 'assigned'] and not x.stage_ref == 'finalized')
        res = super().action_supplier_cancel(cancel_reason_id, reason_text)
        if not global_app_notification_url:
            _logger.warning("No se ha configurado la URL de notificación global a la app")
        if self_filtered and global_app_notification_url:
            self_filtered.action_notify_cancelation_to_app(global_app_notification_url, 'internal')
        return res

    def action_event_cancel(self, cancel_reason_id: int, reason_text=None):
        # Implement: Notify cancel from internal to app
        global_app_notification_url =\
            self.env['ir.config_parameter'].sudo().get_param('ike_event.app.url.global_notification')
        self_filtered = self.filtered(lambda x: x.state in ['accepted', 'assigned'] and not x.stage_ref == 'finalized')
        res = super().action_supplier_cancel(cancel_reason_id, reason_text)
        if not global_app_notification_url:
            _logger.warning("No se ha configurado la URL de notificación global a la app")
        if self_filtered and global_app_notification_url:
            self_filtered.action_notify_cancelation_to_app(global_app_notification_url, 'event')
        return res

    def action_supplier_cancel(self, cancel_reason_id: int, reason_text=None):
        # Implement: Notify cancel from portal to app
        global_app_notification_url =\
            self.env['ir.config_parameter'].sudo().get_param('ike_event.app.url.global_notification')
        self_filtered = self.filtered(
            lambda x: x.state in ['accepted', 'assigned'] and not x.stage_ref == 'finalized'
            and x.supplier_id.x_has_portal is True  # Notificar solo si tiene mesa de control
        )
        res = super().action_supplier_cancel(cancel_reason_id, reason_text)
        if not global_app_notification_url:
            _logger.warning("No se ha configurado la URL de notificación global a la app")
        if self_filtered and global_app_notification_url:
            self_filtered.action_notify_cancelation_to_app(global_app_notification_url, 'portal')
        return res


class IkeEventSupplierElapsedTime(models.Model):
    _name = 'ike.event.supplier.elapsed_time'
    _description = 'Event Supplier Elapsed Time'

    event_id = fields.Many2one('ike.event', required=True)
    vehicle_id = fields.Many2one('fleet.vehicle', required=True)
    stage_id = fields.Many2one('ike.service.stage', required=True)
    app_timestamp = fields.Datetime(required=True)
    elapsed_seconds = fields.Integer(required=True)
    latitude = fields.Char()
    longitude = fields.Char()
