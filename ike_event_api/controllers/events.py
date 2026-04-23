import base64
import requests
from odoo import http, Command, _
from odoo.http import request
from odoo.exceptions import AccessError
from werkzeug.exceptions import (Forbidden, NotFound, BadRequest, InternalServerError, Unauthorized)  # noqa: F401  # type: ignore
from odoo.addons.ike_event_portal.controllers.services_controller import PortalUserAccount  # ajusta el import
import logging
_logger = logging.getLogger(__name__)


class EventAPIController(http.Controller):

    # ====================== #
    #     AUXILIAR METHODS   #
    def _check_operator_assigned_to_event(self, event_sudo, user):
        if event_sudo.selected_supplier_ids.filtered(lambda x: x.truck_id.driver_id.id != user.partner_id.id):
            return BadRequest('User is not assigned to the event supplier')

    @staticmethod
    def _ike_events_get_image_content(img_file):
        """Convierte un archivo de imagen a base64"""
        return base64.b64encode(img_file.read())

    # ===================== #
    #         EVENT         #
    # ===================== #
    @http.route('/ike/event/assistview', type='json', auth='user', methods=['POST'])
    def ike_event_assistview(self, **kw):
        results = kw.get('results', {})
        event_id = kw.get("event_id", False)
        # assistview_id = kw.get("assistview_id", False)
        if not event_id:
            return {'status': 'error', 'message': 'Missing parameters'}

        # event_type = kw.get("event_type", False)
        # event_type 1 = All
        # event_type 2 = Only location
        try:
            openai_data = results.get("openai", {})
            card = openai_data.get("circulation_card", {}).get("data", {})
            vehicle_data = openai_data.get("vehicle_photos", {}).get("data", {})

            brand = vehicle_data.get("brand", "")
            model = vehicle_data.get("model", "")
            year = card.get("model_year", "")
            plates = vehicle_data.get("license_plate", False)
            if not plates:
                plates = card.get("plate", "")
            color = vehicle_data.get("color", "")
            location = kw.get("location", {})

            vehicle_images = kw.get("downloads", {}).get("images", [])
            answers = {
                "movement_obstruction": vehicle_data.get("movement_obstruction", False),
                "movement_obstruction_description": vehicle_data.get("movement_obstruction_description", ""),
                "visible_damage": vehicle_data.get("visible_damage", False),
                "damage_description": vehicle_data.get("damage_description", ""),
            }

            # Descargar imágenes del vehículo en base64
            plate_image_encoded = None

            # Descargar imagenes del vehículo
            plate_image_encoded = None
            vehicle_images_encoded = {}
            temporal_front_image = None
            first_image = None
            i = 0
            for image_data in vehicle_images:
                b64 = self._x_ike_assistview_download_image_b64(image_data['presigned_url'])
                if b64:
                    key = image_data['label']
                    vehicle_images_encoded[key] = b64
                    # Guardar imagen de la placa al iterar
                    if key == 'placa_recorte':
                        plate_image_encoded = b64

                    # Guardar imagen frente para usar en lugar de recorte de placa si no hay
                    if key == 'frente':
                        temporal_front_image = b64
                    # Si no hay clave 'frente' usar primer imagen
                    if i == 0:
                        first_image = b64

                    i += 1

            # Colocar imagen con clave 'frente' si no hay recorte de placa
            if not plate_image_encoded:
                plate_image_encoded = temporal_front_image
            # Si no hay imagen con clave 'frente' usar primer imagen
            if not plate_image_encoded:
                plate_image_encoded = first_image

            message = {
                "id": event_id, "brand": brand, "model": model, "plate": plates, "color": color, "location": location,
                "plate_image": plate_image_encoded, "vehicle_images": vehicle_images_encoded, "answers": answers,
                "year": year,
            }
            _logger.info(f"/ike/event/assistview/{event_id}")

            channel_name = f'ike_channel_assistview_event_{event_id}'
            request.env['bus.bus']._sendone(
                target=channel_name,
                notification_type='ike_event_assistview_reload',
                message=message,
            )
            return {'status': 'ok'}
        except Exception as e:
            _logger.error(f"Error sending assistview event: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def _x_ike_assistview_download_image_b64(self, url):
        """Descarga una imagen desde una URL y retorna base64."""
        if not url:
            return None
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            return base64.b64encode(response.content)
        except Exception as e:
            _logger.warning(f"No se pudo descargar imagen {url}: {str(e)}")
            return None

    @http.route('/ike/event/accept', type='json', auth='user', methods=['POST'])
    def ike_event_accept(self, **kw):
        # Este endpoint se usará para aceptar proveedores externos,
        # se recibirá event_id, vehicle_id, acccepted_datetime, accepted_user,
        # este ultimo será opcional, buscar el usuario del proveedor del vehículo
        # Enviar en la respuesta el código de usuario

        # Validar sesión
        if not request.env.uid:
            request.env.cr.rollback()
            raise Unauthorized(_('Usuario no autenticado'))

        event_id = kw.get('event_id', False)
        vehicle_id = kw.get('vehicle_id', False)
        accepted_datetime = kw.get('accepted_datetime', False)
        # accepted_user = kw.get('accepted_user', "")

        if not event_id or not vehicle_id or not accepted_datetime:
            raise BadRequest(_('Missing parameters'))

        env = request.env

        Supplier = env['ike.event.supplier'].sudo()

        domain = [
            ('event_id', '=', event_id),
            ('truck_id.x_vehicle_ref', '=', vehicle_id),
            ('state', '=', 'notified'),
        ]

        supplier = Supplier.search(domain, limit=1)
        if not supplier:
            raise NotFound(f"No se encontró el proveedor {vehicle_id} para el evento {event_id}")

        try:
            supplier.action_accept()
            # Integrar el envío de ruta, cambia a asignado
            supplier.action_notify_operator()
            # ToDo: Cómo integrar esto? Se necesita guardar la fecha y hora recibida
            supplier.write({'acceptance_date': accepted_datetime})
            return {
                'status': 'success',
                'user_code': supplier.event_id.user_code,
            }
        except Exception as e:
            _logger.error(f"Error on action_accept: {str(e)}")
            raise InternalServerError(str(e))

    # Terminación de recogida
    @http.route('/ike/event/send_end_format', type='http', auth='user', methods=['POST'], csrf=False)
    def ike_event_send_end_format(self, **kw):
        # ToDo: Cómo se integra proveedor de evento?
        service_id = kw.get('service_id', None)
        # user_code = kw.get('user_code', None)
        evidence_images = {
            'front': request.httprequest.files.getlist('front_side_images'),
            'back': request.httprequest.files.getlist('back_side_images'),
            'left': request.httprequest.files.getlist('left_side_images'),
            'right': request.httprequest.files.getlist('right_side_images'),
            'inside': request.httprequest.files.getlist('inside_images'),
        }
        user_sign = request.httprequest.files.get('user_sign')
        extra_paid = kw.get('extra_paid', None)
        extra_paid_amount = kw.get('extra_paid_amount', 0.0)
        comments = kw.get('comments', None)

        if not service_id or not user_sign:
            return request.make_json_response({'error': _('Missing parameters')}, status=400)

        try:  # Convert sevice_id to int
            service_id = int(service_id)
        except ValueError:
            return request.make_json_response({'error': f'service_id must be integer, got: {service_id}'}, status=400)

        if extra_paid:  # Convert extra_paid to bool
            if extra_paid.lower() == 'true':
                extra_paid = True
            elif extra_paid.lower() == 'false':
                extra_paid = False
            else:
                return request.make_json_response({
                    'error': f'extra_paid must be boolean (true, false), got: {extra_paid}'}, status=400)

        if extra_paid_amount:
            try:  # Convert extra_paid_amount to float
                extra_paid_amount = float(extra_paid_amount)
            except ValueError:
                return request.make_json_response({
                    'error': f'extra_paid_amount must be float, got: {extra_paid_amount}'}, status=400)

        event_id = request.env['ike.event'].sudo().browse([service_id])
        event_sudo = event_id.sudo()

        min_required_photos = event_sudo.sub_service_id.x_min_required_photos or 0

        # Validar fotos solo si se requiere al menos 1
        if min_required_photos > 0:
            sides = ('front', 'back', 'left', 'right')
            if any(len(evidence_images[side]) < min_required_photos for side in sides):
                return request.make_json_response({
                    'error': _('Missing images. At least %s image(s) per side are required.') % min_required_photos
                }, status=400)

        self._check_operator_assigned_to_event(event_sudo, request.env.user)

        if not event_sudo.service_evidence_ids.filtered(lambda x: x.evidence_type == 'pickup'):
            detail_ids = []
            for image_side, images in evidence_images.items():
                detail_ids += [Command.create({
                    'file_name': image.filename,
                    'file_image': self._ike_events_get_image_content(image),
                    'side': image_side,
                }) for image in images]

            request.env['ike.event.evidence'].create({
                'event_id': event_id.id,
                'evidence_type': 'pickup',
                # 'nu_user_code': user_code,
                'extra_pay': extra_paid,
                'extra_pay_amount': extra_paid_amount,
                'comments': comments,
                'nu_user_sign': self._ike_events_get_image_content(user_sign),
                'detail_ids': detail_ids,
            })

        return request.make_json_response({
            'service_id': service_id,
            'status': 'success',
        }, status=200)

    # Terminación de servicio
    @http.route('/ike/event/send_end_service', type='http', auth='user', methods=['POST'], csrf=False)
    def ike_event_send_end_service(self, **kw):
        # ToDo: Cómo se integra proveedor de evento?
        service_id = kw.get('service_id', None)
        evidence_images = {
            'front': request.httprequest.files.getlist('front_side_images'),
            'back': request.httprequest.files.getlist('back_side_images'),
            'left': request.httprequest.files.getlist('left_side_images'),
            'right': request.httprequest.files.getlist('right_side_images'),
            'inside': request.httprequest.files.getlist('inside_images'),
        }
        name_of_receive = kw.get('name_of_receive')
        sign_of_receive = request.httprequest.files.get('sign_of_receive')
        comments = kw.get('comments', None)

        if not service_id or not name_of_receive or not sign_of_receive:
            return request.make_json_response({'error': _('Missing parameters')}, status=400)

        try:
            service_id = int(service_id)
        except ValueError:
            return request.make_json_response({'error': f'service_id must be integer, got: {service_id}'}, status=400)

        event_id = request.env['ike.event'].sudo().browse([service_id])
        event_sudo = event_id.sudo()

        min_required_photos = event_sudo.sub_service_id.x_min_required_photos or 0

        # Validar fotos solo si se requiere al menos 1
        if min_required_photos > 0:
            sides = ('front', 'back', 'left', 'right')
            if any(len(evidence_images[side]) < min_required_photos for side in sides):
                return request.make_json_response({
                    'error': _('Missing images. At least %s image(s) per side are required.') % min_required_photos
                }, status=400)

        self._check_operator_assigned_to_event(event_sudo, request.env.user)

        if not event_sudo.service_evidence_ids.filtered(lambda x: x.evidence_type == 'completed'):
            detail_ids = []
            for image_side, images in evidence_images.items():
                detail_ids += [Command.create({
                    'file_name': image.filename,
                    'file_image': self._ike_events_get_image_content(image),
                    'side': image_side,
                }) for image in images]

            request.env['ike.event.evidence'].create({
                'event_id': event_id.id,
                'evidence_type': 'completed',
                'comments': comments,
                'nu_user_sign': self._ike_events_get_image_content(sign_of_receive),
                'detail_ids': detail_ids,
            })

        return request.make_json_response({
            'service_id': service_id,
            'status': 'success'
        }, status=200)

    # Finalizar servicio
    @http.route('/ike/event/end_service', type='json', auth='user', methods=['POST'])
    def ike_event_end_service(self, **kw):
        user = request.env.user
        event_id = kw.get('event_id', False)
        if not event_id:
            raise BadRequest(_('Missing parameters'))

        event = request.env['ike.event'].sudo().browse([event_id])
        event_sudo = event.sudo()

        if not event_sudo:
            raise NotFound(_('Event not found'))

        self._check_operator_assigned_to_event(event_sudo, user)

        if event_sudo.stage_id.ref != 'in_progress':
            raise BadRequest(_('Event not in progress stage'))

        # ToDo: Adaptar a la forma de validar que menciona Nefta para usar el action_forward
        # event_sudo.action_forward()
        return {'status': 'success'}

    @http.route(['/ike/event/end_service/report'], type='http', auth="user", methods=['GET'])
    def api_event_report(self, **kw):
        _logger.warning(f"API request: {kw}")
        event_id = kw.get('event_id', False)
        if not event_id:
            return request.make_json_response({
                'error': _('Missing parameters')
            }, status=400)

        try:
            event = request.env['ike.event'].browse([int(event_id)])
            event.check_access_rights('read')
            event.check_access_rule('read')
        except AccessError:
            return request.make_json_response({
                'error': _('Access denied')
            }, status=403)

        # Verificar que el PDF existe
        if not event.pdf_report_of_finalization:
            return request.make_json_response({
                'error': _('PDF not generated yet')
            }, status=404)

        # El PDF ya está en binario, solo enviarlo directamente
        pdf_content = base64.b64decode(event.pdf_report_of_finalization)

        pdfhttpheaders = [
            ('Content-Type', 'application/pdf'),
            ('Content-Length', len(pdf_content)),
            ('Content-Disposition', f'inline; filename="end_service_{event.name}.pdf"')
        ]

        return request.make_response(pdf_content, headers=pdfhttpheaders)

    @http.route('/ike/event/cancel', type='json', auth='user', methods=['POST'], csrf=False)
    def ike_event_cancel(self, **kw):
        # Validar sesión
        if not request.env.uid:
            request.env.cr.rollback()
            raise Unauthorized(_('Usuario no autenticado'))

        # Parámetros esperados desde la app móvil
        event_id = kw.get('event_id')
        vehicle_id = kw.get('vehicle_id')
        event_supplier_id = kw.get('event_supplier_id')
        cancel_reason_id = kw.get('cancel_reason_id')
        reason_text = kw.get('reason_text')

        # Validar parámetros mínimos
        if not (event_id and vehicle_id and cancel_reason_id):
            raise BadRequest(_('Parámetros requeridos faltantes'))

        env = request.env

        # Buscar el registro de cancel_reason
        cancel_reason = env['ike.event.cancellation.reason'].browse(cancel_reason_id)
        if not cancel_reason.exists():
            raise BadRequest(_('Motivo de cancelación inválido'))

        Supplier = env['ike.event.supplier'].sudo()

        domain = [
            ('event_id', '=', event_id),
            ('truck_id.x_vehicle_ref', '=', vehicle_id),
            ('state', 'in', ('accepted', 'assigned')),
            ('selected', '=', True),
        ]
        if event_supplier_id:
            domain.append(('id', '=', event_supplier_id))

        supplier = Supplier.search(domain, limit=1)
        if not supplier:
            raise NotFound(_('No se encontró el registro de supplier para cancelar'))

        # Ejecutar cancelación
        supplier.action_supplier_cancel(cancel_reason_id=cancel_reason.id, reason_text=reason_text)

        # Puedes devolver algo más específico según tu app móvil
        return {
            'status': 'success',
            'message': _('Servicio cancelado correctamente'),
            'supplier_id': supplier.id,
            'event_id': supplier.event_id.id,
            'vehicle_id': supplier.truck_id.x_vehicle_ref,
        }

    @http.route('/ike/event/reject', type='json', auth='user', methods=['POST'], csrf=False)
    def ike_event_supplier_reject(self, **kw):
        # Validar sesión
        if not request.env.uid:
            request.env.cr.rollback()
            raise Unauthorized(_('Usuario no autenticado'))

        # Parámetros esperados desde la app móvil
        event_id = kw.get('event_id')
        vehicle_id = kw.get('vehicle_id')
        reject_text = kw.get('reject_text')

        # Validar parámetros mínimos
        if not (event_id and vehicle_id and reject_text):
            raise BadRequest(_('Parámetros requeridos faltantes'))

        env = request.env

        Supplier = env['ike.event.supplier'].sudo()

        domain = [
            ('event_id', '=', event_id),
            ('truck_id.x_vehicle_ref', '=', vehicle_id),
            ('state', '=', 'notified'),
        ]

        supplier = Supplier.search(domain, limit=1)
        if not supplier:
            raise NotFound(_('No se encontró el registro de supplier para cancelar'))

        # Ejecutar action_reject
        supplier.action_reject()

        return {
            'status': 'success',
            'message': _('Servicio rechazado correctamente'),
            'event_id': supplier.event_id.id,
            'vehicle_id': supplier.truck_id.x_vehicle_ref,
        }

    # ==========================#
    #      EVENT/CONCEPTS       #
    # ==========================#
    @http.route('/ike/event/concetps/set', type='json', auth='user', methods=['POST'], csrf=False)
    def ike_event_concepts_set(self, **kw):
        """
        Endpoint para registrar conceptos adicionales por evento y proveedor.

        Recibe un payload donde cada clave es un event_id y su valor es una
        lista de suppliers, cada uno con su vehicle_id y los conceptos a registrar.

        Payload esperado:
            {
                "<event_id>": [
                    {
                        "vehicle_id": "<x_vehicle_ref>",
                        "concepts": [
                            {"id": <product_id>, "quantity": <cantidad>},
                            ...
                        ]
                    },
                    ...
                ],
                ...
            }

        Returns:
            dict: {"status": "success", "results": [...]}

        Raises:
            Unauthorized:        Si el usuario no tiene sesion activa.
            BadRequest:          Si el payload no cumple la estructura esperada
                                 o faltan parametros requeridos.
            NotFound:            Si no existe un proveedor activo para el par
                                 (event_id, vehicle_id) recibido.
            InternalServerError: Si ocurre un error inesperado durante la escritura.
        """
        if not request.env.uid:
            request.env.cr.rollback()
            raise Unauthorized(_('Usuario no autenticado'))

        # Valida que el payload tenga la forma correcta antes de consultar BD.
        # Si hay multiples errores de estructura, los acumula todos y los
        # devuelve juntos para que el cliente pueda corregirlos en un solo ciclo.
        self.__validate_concepts_structure(kw)

        # Consulta la BD para verificar que cada (event_id, vehicle_id) tenga
        # un proveedor valido y enriquece el payload con su supplier_id.
        # Ninguna escritura ocurre aqui — si algo falla, no hay nada que revertir.
        self.__resolve_supplier_ids(kw)

        # Con el payload validado y enriquecido, delega la escritura.
        return self.__save_concepts(kw)

    def __validate_concepts_structure(self, data):
        """
        Valida que el payload tenga exactamente la estructura esperada.

        Recorre todos los niveles del payload (eventos, suppliers, concepts)
        acumulando todos los errores encontrados antes de lanzar la excepcion.
        Esto evita el patron "corrige un error, vuelve a intentar, aparece otro"
        que frustra a los consumidores del API.

        Args:
            data (dict): El payload crudo recibido en **kw.

        Raises:
            BadRequest: Si la estructura es invalida. El mensaje incluye la
                        lista completa de errores para facilitar el debug.
        """
        if not isinstance(data, dict) or not data:
            raise BadRequest('Estructura incorrecta: se esperaba un objeto con event_ids como claves')

        errors = []

        for event_key, suppliers in data.items():
            # Las claves del objeto JSON son siempre strings; verificamos
            # que representen un entero valido (el ID del evento en Odoo).
            if not str(event_key).isdigit():
                errors.append(f"Clave de evento invalida: '{event_key}' (debe ser numerica)")
                continue

            if not isinstance(suppliers, list):
                errors.append(f"event_id '{event_key}': se esperaba una lista de suppliers")
                continue

            for i, supplier in enumerate(suppliers):
                prefix = f"event_id '{event_key}', supplier[{i}]"

                if 'vehicle_id' not in supplier:
                    errors.append(f"{prefix}: falta 'vehicle_id'")

                concepts = supplier.get('concepts')
                if not isinstance(concepts, list) or not concepts:
                    errors.append(f"{prefix}: 'concepts' debe ser una lista no vacia")
                    continue

                for j, concept in enumerate(concepts):
                    c_prefix = f"{prefix}, concept[{j}]"

                    if 'id' not in concept:
                        errors.append(f"{c_prefix}: falta 'id'")
                    if 'quantity' not in concept:
                        errors.append(f"{c_prefix}: falta 'quantity'")
                    if not isinstance(concept.get('id'), int):
                        errors.append(f"{c_prefix}: 'id' debe ser entero")
                    if not isinstance(concept.get('quantity'), (int, float)):
                        errors.append(f"{c_prefix}: 'quantity' debe ser numerico")

        if errors:
            _logger.warning(f"Payload rechazado por estructura invalida: {errors}")
            raise BadRequest(f"Estructura de datos incorrecta: {errors}")

        _logger.info(f"Payload valido. Events recibidos: {list(data.keys())}")

    def __resolve_supplier_ids(self, data):
        """
        Verifica la existencia de proveedores y enriquece el payload con su ID interno.

        Para cada par (event_id, vehicle_id) del payload, busca en ike.event.supplier
        un registro activo (estado accepted/assigned, seleccionado). Si lo encuentra,
        agrega 'supplier_id' al dict del supplier para que __save_concepts lo use
        directamente sin necesidad de volver a consultar la BD.

        Se usa sudo() porque el usuario de la app movil puede no tener acceso
        directo al modelo ike.event.supplier, pero la logica de negocio garantiza
        que la operacion es valida para su sesion.

        Args:
            data (dict): Payload ya validado por __validate_concepts_structure.
                         Se modifica in-place agregando 'supplier_id' a cada supplier.

        Raises:
            BadRequest: Si vehicle_id o concepts estan vacios (no deberia ocurrir
                        tras la validacion de estructura, pero se guarda como
                        segunda linea de defensa).
            NotFound:   Si no existe un proveedor activo para el par (event_id, vehicle_id).
        """
        Supplier = request.env['ike.event.supplier'].sudo()

        for event_key, suppliers_data in data.items():
            event_id = int(event_key)
            for supplier_data in suppliers_data:
                vehicle_id = supplier_data.get('vehicle_id')
                concepts = supplier_data.get('concepts', [])

                if not vehicle_id or not concepts:
                    _logger.warning(f"Evento {event_id}: faltan parametros en supplier_data")
                    raise BadRequest('Faltan parametros')

                supplier = Supplier.search([
                    ('event_id', '=', event_id),
                    ('truck_id.x_vehicle_ref', '=', vehicle_id),
                    # Solo proveedores que hayan aceptado y esten asignados al evento
                    ('state', 'in', ('accepted', 'assigned')),
                    ('selected', '=', True),
                ], limit=1)

                if not supplier:
                    raise NotFound(_(
                        f"No se encontro proveedor activo para evento {event_id}, vehiculo '{vehicle_id}'"
                    ))

                # Enriquecemos el dict original para no tener que repetir
                # la consulta a BD en el paso de escritura.
                supplier_data['supplier_id'] = supplier.supplier_id.id

    def __save_concepts(self, data):
        """
        Persiste los conceptos adicionales llamando al controlador de portal.

        Delega la creacion de cada concepto a PortalUserAccount.create_concept,
        que contiene la logica de negocio de creacion (validaciones de producto,
        precios, lineas de pedido, etc.). Este metodo solo orquesta las llamadas
        y agrega los resultados.

        El try/except aqui unicamente captura errores inesperados (fallo de BD,
        bug en create_concept, etc.). Los errores de negocio esperados deben
        lanzarse antes de llegar a este punto.

        Args:
            data (dict): Payload validado y enriquecido con supplier_id.

        Returns:
            dict: {"status": "success", "results": [...]}, donde results contiene
                  la respuesta de create_concept por cada concepto procesado.

        Raises:
            InternalServerError: Si ocurre cualquier excepcion no anticipada
                                 durante la escritura. Hace rollback antes de lanzar.
        """
        try:
            controller = PortalUserAccount()
            results = []

            for event_key, suppliers_data in data.items():
                event_id = int(event_key)
                for supplier_data in suppliers_data:
                    for concept in supplier_data.get('concepts', []):
                        result = controller.create_concept(
                            event_id=event_id,
                            supplier_id=supplier_data.get('supplier_id'),
                            product_id=concept.get('id'),
                            quantity=concept.get('quantity'),
                        )
                        results.append(
                            dict(
                                result,
                                event_id=event_id,
                                vehicle_id=supplier_data.get('vehicle_id'),
                                concept_id=concept.get('id'),
                                quantity=concept.get('quantity'),
                            )
                        )

            _logger.info(f"Concepts creados exitosamente: {len(results)} registros")
            return {'status': 'success', 'results': results}

        except Exception as e:
            # Revertimos cualquier escritura parcial que haya ocurrido
            # antes del error para mantener consistencia en la BD.
            request.env.cr.rollback()
            _logger.error(f"Error inesperado al crear concepts: {str(e)}", exc_info=True)
            raise InternalServerError("Error interno al crear conceptos")

    # ============================ #
    #         EVENT/DRIVER         #
    # ============================ #
    @http.route('/ike/event/driver/assign', type='json', auth='user', methods=['POST'])
    def ike_event_driver_assign(self, **kw):
        return {'status': 'Not implemented yet'}

    # ============================= #
    #         EVENT/VEHICLE         #
    # ============================= #
    @http.route('/ike/event/vehicle/send_collection', type='json', auth='user', methods=['POST'])
    def ike_event_vehicle_send_collection(self, **kw):
        return {'status': 'Not implemented yet'}
