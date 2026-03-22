import base64
from odoo import http, Command, _
from odoo.http import request
from odoo.exceptions import AccessError
from werkzeug.exceptions import (Forbidden, NotFound, BadRequest, InternalServerError, Unauthorized)  # noqa: F401  # type: ignore
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
        # event_type = kw.get("event_type", False)
        # event_type 1 = All
        # event_type 2 = Only location
        card = results.get("circulation_card", {}).get("document", {})
        vehicle = results.get("vehicle_analysis", {}).get("vehicle", {})

        brand = vehicle.get("brand", "")
        model = vehicle.get("model", "")
        plates = card.get("plate", "")
        color = vehicle.get("color", "")
        location = results.get("vehicle_analysis", {}).get("location_center", {})
        answers = {
            "movement_obstruction": vehicle.get("movement_obstruction", False),
            "movement_obstruction_description": vehicle.get("movement_obstruction_description", ""),
            "visible_damage": vehicle.get("visible_damage", False),
            "damage_description": vehicle.get("damage_description", ""),
        }

        if not event_id:
            return {'status': 'error', 'message': 'Missing parameters'}

        try:
            message = {
                "id": event_id, "brand": brand, "model": model, "plate": plates, "color": color, "location": location,
                "answers": answers
            }
            _logger.info(f"/ike/event/assistview/{event_id}")
            _logger.info(f"assistivew message: {message}")

            channel_name = f'ike_channel_assistview_event_{str(event_id)}'
            request.env['bus.bus']._sendone(
                target=channel_name,
                notification_type='ike_event_assistview_reload',
                message=message,
            )
            return {'status': 'ok'}
        except Exception as e:
            _logger.error(f"Error sending assistivew event: {str(e)}")
            return {'status': 'error', 'message': str(e)}
        # return {'status': 'Not implemented yet'}

    @http.route('/ike/event/accept', type='json', auth='user', methods=['POST'])
    def ike_event_accept(self, **kw):
        # ToDo: Recibir el valor de event_supplier_id, para saber quien aceptó
        # ToDo: Detonar el 'action_accept' de esa linea, para que se le asigne el evento
        # ToDo: Ejecutar el 'action_forward' del evento
        user = request.env.user
        event_id = kw.get('event_id', False)
        # vehicle_id = kw.get('vehicle_id', False)  # ToDo: Para obtener linea de proveedor
        event_supplier_id = kw.get('event_supplier_id', False)
        if not event_id:
            raise BadRequest(_('Missing parameters'))

        event = request.env['ike.event'].sudo().browse([event_id])
        event_sudo = event.sudo()

        if not event_sudo:
            raise NotFound(_('Event not found'))

        self._check_operator_assigned_to_event(event_sudo, user)

        if event_sudo.stage_id.ref != 'assigned':
            raise BadRequest(_('Event not in assigned stage'))

        # ToDo: Adaptar a la forma de validar que menciona Nefta para usar el action_forward
        # event_sudo.action_forward()

        if event_supplier_id:
            event_supplier = request.env['ike.event.supplier'].sudo().browse([event_supplier_id])
            event_supplier_sudo = event_supplier.sudo()
            if not event_supplier_sudo:
                raise NotFound(_('Event Supplier not found'))
            if event_supplier_sudo.state != 'notified':
                raise BadRequest(_('Event Supplier not notified to accept'))
            event_supplier_sudo.action_accept()

        return {'status': 'success'}

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
