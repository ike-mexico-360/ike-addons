import requests
from odoo import models, _
import logging
_logger = logging.getLogger(__name__)


class IkeServiceInputVial(models.Model):
    _inherit = 'ike.service.input.vial'

    def x_send_request_to_create_session(
        self,
        event_id: str,
        min_required_photos: int,
        assistview_id,
        request_lambda_session: bool,
        request_whatsapp_message: bool,
        template: int,
        phone_number: str
    ):
        url = self.env['ir.config_parameter'].sudo().get_param('assistview.lambda.session')
        if not url:
            _logger.warning("No se ha configurado la URL para crear la sessión del lambda deprocesamiento para el Assistview")
            return False
        if url:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Python-IoT-Test/1.0",
            }
            encryption_util = self.env['custom.encryption.utility']
            body = {
                "phone": phone_number,
                "reference": event_id,
                "assistview_id": str(assistview_id.id),
                "template_id": template,
                "type_id": 1,
                "nombre": encryption_util.decrypt_aes256(self.event_id.user_id.name),
                "min_required_photos": min_required_photos,
            }

            send_whatsapp_message = False

            # Si ya existe sesión de lambda, si se necesita enviar el mensaje, marcamos como True
            if request_whatsapp_message and not send_whatsapp_message:
                send_whatsapp_message = True

            if request_lambda_session:
                try:
                    _logger.info(f"Assistview: Sending request to create session at lambda: {body}")
                    session_response = requests.post(url, headers=headers, json=body)
                    response_data = session_response.json()
                    if response_data.get('status') == 'ok':
                        send_whatsapp_message = True
                        assistview_id.write({'created_lambda_session': True})
                        _logger.info(f"Session created successfully: {response_data}")
                    else:
                        if response_data.get('existing_session', False):
                            send_whatsapp_message = True
                            assistview_id.write({'created_lambda_session': True})
                            _logger.info(f"Session created successfully: {response_data}")
                        else:
                            send_whatsapp_message = False
                            _logger.warning(f"Error al crear sesión {response_data}")
                except Exception as e:
                    send_whatsapp_message = False
                    _logger.error(f"Assistview: Error to send request at lambda: {str(e)}")

            if request_whatsapp_message and send_whatsapp_message:
                wp_access_token = self.env['ike.event.supplier'].x_get_whatsapp_token()
                successfully_sent = self.env['ike.event.supplier'].x_send_whatsapp_template(
                    access_token=wp_access_token,
                    event_id=event_id,
                    template=template,
                    phone_number=phone_number,
                )
                if successfully_sent:
                    assistview_id.write({'sended_whatsapp_message': True})
                return successfully_sent

            # Si no se creará la sesión ni se enviará mensaje, devolvermos True, para abir el wizard
            if not request_lambda_session and not request_whatsapp_message:
                return True

        return False

    def action_identification_whatsapp(self):
        super().action_identification_whatsapp()
        self.ensure_one()
        enable_assistview = bool(self.env['ir.config_parameter'].sudo().get_param('assistview.enable'))
        if not enable_assistview:
            _logger.info("Assistview: Deshabilitado assistview.enable = False")
        if enable_assistview:
            try:
                decrypt_encrypt_utility_sudo = self.env['custom.encryption.utility'].sudo()
                phone_number = decrypt_encrypt_utility_sudo.decrypt_aes256(self.event_id.user_id.phone or '')
                if phone_number:
                    phone_number = phone_number.replace(' ', '')
                assistview_data = self._x_ike_create_assistview()
                _logger.info(f"Assistview: {assistview_data}")
                request_lambda_session = assistview_data['request_lambda_session']
                min_required_photos = self.event_id.sub_service_id.x_min_required_photos_assistview
                request_whatsapp_message = assistview_data['request_whatsapp_message']
                sended = self.x_send_request_to_create_session(
                    event_id=str(self.event_id.id),
                    min_required_photos=min_required_photos,
                    assistview_id=assistview_data['id'],
                    request_lambda_session=request_lambda_session,
                    request_whatsapp_message=request_whatsapp_message,
                    template=66,  # inicioproceso
                    phone_number=phone_number
                )
                if sended:
                    return {
                        'name': _("Assistview"),
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'res_model': 'ike.event.service.assistview',
                        'res_id': assistview_data['id'].id,
                        'view_id': self.env.ref('ike_event_api.ike_event_service_assistview_view_form').id,
                        'context': {
                            'default_event_id': self.event_id.id,
                        },
                        'target': 'new',
                    }
            except Exception as e:
                _logger.error(f"Assistview: Error sending assistivew event: {str(e)}")

    def _x_ike_create_assistview(self):
        request_lambda_session = False  # Se necesita crear una sesión para el proccesamiento
        request_whatsapp_message = False  # Se necesita enviar el mensaje de whatsapp

        # Existe el wizard
        assistview_id = self.env['ike.event.service.assistview'].search([
            ('event_id', '=', self.event_id.id),
            ('service_res_id', '=', self.id),
            ('service_res_model', '=', 'ike.service.input.vial'),
        ], limit=1, order='id asc')

        # Se crea el wizard
        if not assistview_id:
            assistview_id = self.env['ike.event.service.assistview'].create({
                'event_id': self.event_id.id,
                'service_res_id': self.id,
                'service_res_model': 'ike.service.input.vial',
                'received_assistview': False,
            })

        # Ya existe sesión?
        request_lambda_session = not assistview_id.created_lambda_session
        # Se envió el mensaje solicitando datos?
        request_whatsapp_message = not assistview_id.sended_whatsapp_message

        return {
            'id': assistview_id,
            'request_lambda_session': request_lambda_session,
            'request_whatsapp_message': request_whatsapp_message,
        }

    def test_lambda_session(self):
        """ Función que implementa la prueba de creación de sesiónes para pruebas de cambios en los lambdas
        No tendrá funcionalidad en producción, se usa para testear cambios en los lambdas antes de implementar """

        self.ensure_one()

        lambda_url = self.env['ir.config_parameter'].sudo().get_param('assistview.lambda.session')
        if not lambda_url:
            _logger.warning("No se ha configurado la URL para crear la sessión del lambda deprocesamiento para el Assistview")
            return False

        allow_lambda_test = bool(self.env['ir.config_parameter'].sudo().get_param('assistview.lambda.test.enable'))
        if not allow_lambda_test:
            _logger.info("Assistview: Deshabilitado assistview.lambda.test.enable = False")
            return False

        meta_url = self.env['ir.config_parameter'].sudo().get_param('assistview.lambda.test.meta_url')
        if not meta_url:
            _logger.warning("No se ha configurado la URL para obtener la metadata del lambda deprocesamiento para el Assistview")
            return False

        meta_token = self.env['ir.config_parameter'].sudo().get_param('assistview.lambda.test.meta_token')
        if not meta_token:
            _logger.warning("No se ha configurado el token para obtener la metadata del lambda deprocesamiento para el Assistview")
            return False

        meta_whithelist_number = self.env['ir.config_parameter'].sudo().get_param('assistview.lambda.test.meta_whithelist_number')
        if not meta_whithelist_number:
            _logger.warning("No se ha configurado el numero de telefono para obtener la metadata del lambda deprocesamiento para el Assistview")
            return False

        decrypt_encrypt_utility_sudo = self.env['custom.encryption.utility'].sudo()
        user_name = decrypt_encrypt_utility_sudo.decrypt_aes256(self.event_id.user_id.name or '')
        assistview_data = self._x_ike_create_assistview()

        lambda_headers = {
            "Content-Type": "application/json",
            "User-Agent": "Python-IoT-Test/1.0",
        }
        lambda_body = {
            "phone": meta_whithelist_number,
            "reference": self.event_id.id,
            "assistview_id": str(assistview_data['id'].id),
            "template_id": 66,
            "type_id": 1,
            "nombre": user_name,
            "min_required_photos": 5,
        }
        session_response = requests.post(lambda_url, headers=lambda_headers, json=lambda_body)
        if session_response.status_code != 200:
            _logger.warning(f"Assistview: Error al enviar petición: {session_response.status_code}")
            _logger.warning(f"Assistview: Error al enviar petición: {session_response.text}")
            return False
        else:
            _logger.info(f"Assistview: Session created successfully: {session_response.text}")

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Python-IoT-Test/1.0",
            "Authorization": f"Bearer {meta_token}",
        }

        body = {
            "messaging_product": "whatsapp",
            "to": meta_whithelist_number,
            "type": "template",
            "template": {
                "name": "asistencia_ike_inicio",
                "language": {"code": "es_MX"},
                "components": [
                    {"type": "body", "parameters": [{"type": "text", "text": user_name}]}
                ],
            },
        }

        _logger.info(f"Assistview: Sending request to create session at lambda (TEST): {body}")

        meta_response = requests.post(meta_url, headers=headers, json=body)
        if meta_response.status_code != 200:
            _logger.warning(f"Assistview: Error al enviar petición: {meta_response.status_code}")
            _logger.warning(f"Assistview: Error al enviar petición: {meta_response.text}")
            return False
        else:
            _logger.info(f"Assistview: Meta created successfully: {meta_response.text}")

        return {
            'name': _("Assistview"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'ike.event.service.assistview',
            'res_id': assistview_data['id'].id,
            'view_id': self.env.ref('ike_event_api.ike_event_service_assistview_view_form').id,
            'context': {
                'default_event_id': self.event_id.id,
            },
            'target': 'new',
        }
