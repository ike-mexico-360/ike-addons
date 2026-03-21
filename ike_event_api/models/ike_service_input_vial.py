import requests
from odoo import models, _
import logging
_logger = logging.getLogger(__name__)


class IkeServiceInputVial(models.Model):
    _inherit = 'ike.service.input.vial'

    def x_test_template1(self):
        # Inicio
        phone_number = "5564146854"
        self.x_send_request_to_create_session(str(self.event_id.id), 66, phone_number)

    def x_test_template2(self):
        # Coordenadas
        phone_number = "5564146854"
        self.x_send_request_to_create_session(str(self.event_id.id), 67, phone_number)

    def x_test_template3(self):
        # Confirmación
        phone_number = "5564146854"
        self.x_send_request_to_create_session(str(self.event_id.id), 68, phone_number)

    def x_send_request_to_create_session(self, event_id: str, template: int, phone_number: str):
        url = self.env['ir.config_parameter'].sudo().get_param('assistview.lambda.session')
        if not url:
            url = "https://dc77myufvf.execute-api.us-east-1.amazonaws.com/prod/crearSesion"
        if url:
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Python-IoT-Test/1.0",
            }
            encryption_util = self.env['custom.encryption.utility']
            body = {
                "phone": phone_number,
                "reference": event_id,
                "template_id": template,
                "type_id": 1,
                "nombre": encryption_util.decrypt_aes256(self.event_id.user_id.name),
            }

            call_api_hub = False
            try:
                session_response = requests.post(url, headers=headers, json=body)
                response_data = session_response.json()
                if response_data.get('status') == 'ok':
                    call_api_hub = True
                    _logger.info(f"Session created successfully: {response_data}")
            except Exception as e:
                call_api_hub = False
                _logger.error(f"Error al enviar petición: {str(e)}")

            if call_api_hub:
                sended = self.x_send_to_whatsapp_service(event_id, template, phone_number)
                return sended
        return False

    def x_send_to_whatsapp_service(self, event_id: str, template: int, phone_number: str):
        # ToDo: Mover urls a parámetro de sistema
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Python-IoT-Test/1.0",
        }
        # wa_login_url = self.env['ir.config_parameter'].sudo().get_param('assistview.wa.login_url')
        # wa_template_url = self.env['ir.config_parameter'].sudo().get_param('assistview.wa.template_url')
        login_url = "https://wapp-qa.dev-pruebas.com/login"
        userName = self.env['ir.config_parameter'].sudo().get_param('tt.wp.u')
        password = self.env['ir.config_parameter'].sudo().get_param('tt.wp.p')
        login_body = {
            "userName": userName,
            "password": password
        }
        if not userName or not password:
            _logger.error("Error al obtener credenciales de usuario")

        accessToken = False
        try:
            login_response = requests.post(login_url, headers=headers, json=login_body)
            data_login = login_response.json()
            accessToken = data_login.get('data', {}).get('accessToken', False)
        except Exception as e:
            _logger.error(f"Error al enviar petición: {str(e)}")

        if not accessToken:
            _logger.error(f"Error al obtener el token de acceso: {data_login}")
            return

        send_test_url = "https://wapp-qa.dev-pruebas.com/template"
        send_data = {
            "identifier": {
                "appId": 17,
                "tenants": "adff7f6a-e97d-11eb-9a03-0242ac130003",
                "reference": event_id,
            },
            "petition": {
                "phoneNumber": phone_number,
                "templateId": template,
            }
        }
        try:
            send_response = requests.post(send_test_url, headers=dict(headers, Authorization=accessToken), json=send_data)
            send_data = send_response.json()
            _logger.info(f"send_data: {send_data}")
            return True
        except Exception as e:
            _logger.error(f"Error enviando petición: {str(e)}")
            return False

    def action_identification_whatsapp(self):
        super().action_identification_whatsapp()
        self.ensure_one()
        enable_assistview = bool(self.env['ir.config_parameter'].sudo().get_param('assistview.enable'))
        if enable_assistview:
            # url = "https://zewwh2yw23.execute-api.us-east-1.amazonaws.com/prod/whatsapp-asistencia-ike"
            # headers = {
            #     "Content-Type": "application/json",
            #     "User-Agent": "Python-IoT-Test/1.0",
            # }
            # name = self.event_id.user_id.name
            # phone = self.event_id.user_phone
            # if self.event_id.user_by == 'by_other':
            #     name = self.event_id.user_additional_name
            #     phone = self.event_id.user_additional_phone
            # body = {
            #     "phone": phone,
            #     "nombre": name,
            #     "event_id": self.event_id.id,
            #     "event_type": 1,
            # }
            try:
                # response = requests.post(url, headers=headers, json=body)
                # _logger.info(f"Whatsapp payload: {body}")
                # _logger.info(f"Whatsapp response: {response.json()}")
                # status = response.json().get('status', False)
                phone_number = "5564146854"
                sended = self.x_send_request_to_create_session(str(self.event_id.id), 66, phone_number)
                if sended:
                    return {
                        'name': _("Assistview"),
                        'type': 'ir.actions.act_window',
                        'view_mode': 'form',
                        'res_model': 'ike.event.service.assistview',
                        'view_id': self.env.ref('ike_event_api.ike_event_service_assistview_view_form').id,
                        'context': {
                            'default_event_id': self.event_id.id,
                            'default_service_res_id': self.id,
                            'default_service_res_model': 'ike.service.input.vial',
                        },
                        'target': 'new',
                    }
            except Exception as e:
                _logger.error(f"Error sending assistivew event: {str(e)}")
