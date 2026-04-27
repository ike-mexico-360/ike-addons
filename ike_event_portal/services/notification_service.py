# -*- coding: utf-8 -*-
import requests
import logging

_logger = logging.getLogger(__name__)


class NotificationService:
    """Service to send notifications via AWS Lambda"""

    LAMBDA_ENDPOINT = "https://bebinuoce9.execute-api.us-east-2.amazonaws.com/default/ike_trk_prd_lambda_send_user_notification"

    @staticmethod
    def send_user_notification(user_id, vehicle_id, event):
        """
        Send notification to user about a vehicle assignment

        :param user_id: ID of the user
        :param vehicle_id: ID of the vehicle
        :param event: Dictionary containing event data with keys:
                     - service_id: ID del evento
                     - ca_id: Centro de atención
                     - lng: Longitud de recolección
                     - lat: Latitud de recolección
                     - dst_lng: Longitud de destino
                     - dst_lat: Latitud de destino
                     - control: Mesa de control
                     - assignation_type: Tipo de asignación
                     - estatus: Status del evento
                     - event_supplier_id: ID de la línea del modelo ike.event.supplier
                     - user_code: Código de usuario
        :return: Response from Lambda or False if failed
        """
        try:
            # Query parameters
            params = {
                'user_id': user_id[0],
                'vehicle_id': vehicle_id[0]
            }

            # Request payload (body)
            payload = {
                "service_id": event.get('service_id'),
                "ca_id": event.get('ca_id'),
                "lng": event.get('lng'),
                "lat": event.get('lat'),
                "dst_lng": event.get('dst_lng'),
                "dst_lat": event.get('dst_lat'),
                "control": event.get('control'),
                "assignation_type": event.get('assignation_type'),
                "estatus": event.get('estatus'),
                "event_supplier_id": event.get('event_supplier_id'),
                "user_code": event.get('user_code')
            }

            _logger.info(f"Sending notification to Lambda: user_id={user_id}, vehicle_id={vehicle_id}")
            _logger.info(f"Payload: {payload}")

            # POST request with params and JSON body
            response = requests.post(
                NotificationService.LAMBDA_ENDPOINT,
                params=params,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )

            response.raise_for_status()  # Raise exception for 4XX/5XX status codes

            _logger.info(f"Lambda response: {response.status_code} - {response.text}")

            return response.json() if response.content else True

        except requests.exceptions.Timeout:
            _logger.error("Lambda request timed out")
            return False
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error calling Lambda: {str(e)}")
            return False
