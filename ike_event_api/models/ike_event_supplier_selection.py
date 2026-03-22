# -*- coding: utf-8 -*-

import json
from odoo import models, fields
import requests

import logging

_logger = logging.getLogger(__name__)


class IkeEventSupplierSelection(models.Model):
    _inherit = 'ike.event.supplier'

    notification_sent_to_app = fields.Boolean(string="Notification sent to app", default=False)

    def _is_db_neutralized(self):
        return self.env['ir.config_parameter'].sudo().get_param('database.is_neutralized')

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
        _logger.warning(f"Sending route payload: {json_data}")
        return response.json()

    def action_notify_operator(self):
        # Realizamos el proces antes del super, ya que después del super, el filtrado de self_filtered se complicaría,
        # ya que se le cambia el valor al estado

        self_filtered = self.filtered(lambda x: x.state == 'accepted' and not x.notification_sent_to_app)

        supplier_responses = []  # ToDo: Manejar errores en caso de haber, qué se hará si hay error en alguno?
        tracking_responses = []  # ToDo: Manejar errores en caso de haber, qué se hará si hay error en alguno?
        url_notifications = self.env['ir.config_parameter'].sudo().get_param('ike_event.app.url.notification')
        url_route_tracking = "https://pli43l7mc2.execute-api.us-east-2.amazonaws.com/planned-route"
        if url_notifications and not self._is_db_neutralized():  # No ejecutar si está neutralizado
            for s in self_filtered:
                if s.truck_id.driver_id and s.supplier_id.x_has_portal is True:
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
            for response in supplier_responses:  # ToDo: Quitar esto, solo se utiliza para verificar que se envíe
                _logger.info(f"Notified by portal: {response}")
                # En el log debemos ver algo como:
                # {
                #     'success': True,
                #     'message': 'Event published to IoT Core',
                #     'topic': 'vehiculos/2/27',
                #     'method': 'default_endpoint',
                #     'request_id': '71e29af8-24a5-4fec-b821-a2563b8e2473'
                # }

        # ToDo: Prueba temporal, unificar con el bloque anterior
        if url_route_tracking and not self._is_db_neutralized():  # No ejecutar si está neutralizado
            for s in self_filtered:
                if not s.route:
                    continue
                if s.truck_id.driver_id:
                    _logger.warning(f"Preparando ruta para {s.truck_id.license_plate}")
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
            for response in tracking_responses:  # ToDo: Quitar esto, solo se utiliza para verificar que se envíe
                _logger.info(f"Tracking route: {response}")

        return super(IkeEventSupplierSelection, self).action_notify_operator()

    def action_cancel(self, cancel_reason_id: int, reason_text=None):
        # Implement: Notify cancel from internal to app
        global_app_notification_url =\
            self.env['ir.config_parameter'].sudo().get_param('ike_event.app.url.global_notification')
        self_filtered = self.filtered(lambda x: x.state in ['accepted', 'assigned'] and not x.stage_ref == 'finalized')
        res = super(IkeEventSupplierSelection, self).action_supplier_cancel(cancel_reason_id, reason_text)
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
        res = super(IkeEventSupplierSelection, self).action_supplier_cancel(cancel_reason_id, reason_text)
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
        res = super(IkeEventSupplierSelection, self).action_supplier_cancel(cancel_reason_id, reason_text)
        if not global_app_notification_url:
            _logger.warning("No se ha configurado la URL de notificación global a la app")
        if self_filtered and global_app_notification_url:
            self_filtered.action_notify_cancelation_to_app(global_app_notification_url, 'portal')
        return res

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


class IkeEventSupplierElapsedTime(models.Model):
    _name = 'ike.event.supplier.elapsed_time'
    _description = 'Event Supplier Elapsed Time'

    event_id = fields.Many2one('ike.event', required=True)
    vehicle_id = fields.Many2one('fleet.vehicle', required=True)
    stage_id = fields.Many2one('ike.service.stage', required=True)
    app_timestamp = fields.Datetime(required=True)
    elapsed_seconds = fields.Integer(required=True)
