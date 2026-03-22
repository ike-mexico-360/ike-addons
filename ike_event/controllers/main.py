# -*- coding: utf-8 -*-

import json
import logging
import requests
import time

from odoo.http import request, route, Controller

_logger = logging.getLogger(__name__)


class MainController(Controller):
    @route("/ike_event/get_google_map_api_key", type="json", auth="user")
    def get_google_map_api_key(self):
        return {
            'api_key': request.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')
        }

    @route('/openai/assistant/call_test', type='http', auth='user', methods=['POST'], csrf=False)
    def call_assistant(self, **kwargs):
        """Endpoint para llamar al OpenAI Assistant"""
        open_ai_base_url = 'https://api.openai.com/v1'
        thread_id = None
        headers = {}
        try:
            survey = request.get_json_data() or {}

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
                Analiza el siguiente JSON de solicitud y determina el tipo de unidad que debe atender el servicio,
                aplicando las reglas del archivo IKE.txt.

                Devuelve la respuesta únicamente en el siguiente formato JSON exacto:
                {"id": <id>, "truck_type": ["<valor>"]}

                Si no existe coincidencia clara, responde:
                {"id": <id>, "truck_type": [""]}

                Entrada:
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
