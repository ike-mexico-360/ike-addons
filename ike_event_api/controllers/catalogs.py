from odoo.tools import SQL
from odoo import http, fields, _
from odoo.http import request
from odoo.tools import html2plaintext
from werkzeug.exceptions import (BadRequest, InternalServerError, NotFound, Forbidden, Unauthorized)  # type: ignore
from .LocationBatcher import VehicleLocationBatcher
import logging

_logger = logging.getLogger(__name__)

vehicle_location_batcher = VehicleLocationBatcher()

PROGRESS_STATES_MAP_STAGE = {
    '0': 'ike_event.ike_service_stage_assigned',
    '1': 'ike_event.ike_service_stage_on_route',
    '2': 'ike_event.ike_service_stage_arrived',
    '3': 'ike_event.ike_service_stage_contacted',
    '4': 'ike_event.ike_service_stage_on_route_2',
    '5': 'ike_event.ike_service_stage_arrived_2',
    '6': 'ike_event.ike_service_stage_finalized',
}
PROGRESS_STATES_MAP_REVERSE = {v: k for k, v in PROGRESS_STATES_MAP_STAGE.items()}


# TODO: Cambiar al modelo público
class CatalogsAPIController(http.Controller):

    # ===================== #
    #       AUXILIARS       #
    def _ike_get_query_for_supplier_vehicles(self, supplier_id):
        return """
            SELECT
                fv.id
                ,fv.x_vehicle_ref
                ,fv.name
                ,rps.id AS supplier_id
                ,rps.name AS supplier_name
                ,rp.id AS driver_id
                ,rp.name AS driver_name
                ,ca.id AS ca_id
                ,ca.name AS ca_name
                ,fv.brand_id
                ,fvmb.name AS brand_name
                ,fv.model_id
                ,fvm.name AS model_name
                ,fv.license_plate
                ,fv.x_vehicle_service_state AS service_state
            FROM
                fleet_vehicle fv
            LEFT JOIN res_partner rp ON fv.driver_id = rp.id
            LEFT JOIN res_partner rps ON fv.x_partner_id = rps.id
            LEFT JOIN res_partner ca ON fv.x_center_id = ca.id
            LEFT JOIN fleet_vehicle_model fvm ON fv.model_id = fvm.id
            LEFT JOIN fleet_vehicle_model_brand fvmb ON fvm.brand_id = fvmb.id
            WHERE fv.x_partner_id = %s
                AND (fv.x_vehicle_service_state IS NULL
                OR fv.x_vehicle_service_state != 'disabled');
        """ % (supplier_id,)

    def _prepare_ike_vehicle_data_response(self, base_url, vehicle):
        return {
            'id': vehicle['x_vehicle_ref'] or '',
            'name': vehicle['name'] or '',
            'supplier_id': vehicle['supplier_id'] or False,
            'supplier_name': vehicle['supplier_name'] or '',
            'ca_id': vehicle['ca_id'] or 0,
            'ca_name': vehicle['ca_name'] or '',
            'driver_id': vehicle['driver_id'] or False,
            'driver_name': vehicle['driver_name'] or False,
            'brand_id': vehicle['brand_id'] or False,
            'brand_name': vehicle['brand_name'] or '',
            'model_id': vehicle['model_id'] or False,
            'model_name': vehicle['model_name'] or '',
            'license_plate': vehicle['license_plate'] or False,
            'service_state': vehicle['service_state'] or '',
            'image_128': "%s/web/image/fleet.vehicle/%s/image_128" % (base_url, vehicle['id']),
        }

    def _ike_event_supplier_line_id(self, event_id, vehicle_id):
        request.env.cr.execute("""
            SELECT ies.id, ies.stage_id
            FROM ike_event_supplier ies
            INNER JOIN fleet_vehicle fv ON fv.id = ies.truck_id
            WHERE
                ies.event_id = %(event_id)s
                AND fv.x_vehicle_ref = %(vehicle_id)s
                AND ies.state = 'assigned'
            LIMIT 1;
        """, {'event_id': event_id, 'vehicle_id': vehicle_id})
        return request.env.cr.dictfetchone()

    def _ike_get_auxiliary_query_for_progress_state(self):
        """ Auxiliar para mapear el res_id con el progress_state """
        select_clause = """
            CASE
                WHEN imd.name = 'ike_service_stage_assigned' THEN
                    '0'
                WHEN imd.name = 'ike_service_stage_on_route' THEN
                    '1'
                WHEN imd.name = 'ike_service_stage_arrived' THEN
                    '2'
                WHEN imd.name = 'ike_service_stage_contacted' THEN
                    '3'
                WHEN imd.name = 'ike_service_stage_on_route_2' THEN
                    '4'
                WHEN imd.name = 'ike_service_stage_arrived_2' THEN
                    '5'
                WHEN imd.name = 'ike_service_stage_finalized' THEN
                    '6'
                ELSE '-1'
            END as progress_state
        """
        inner_clause = """
            LEFT JOIN ir_model_data imd ON imd.res_id = supplier.stage_id
                AND imd.model = 'ike.service.stage'
                AND imd.module = 'ike_event'
        """
        return select_clause, inner_clause

    def _get_xmlid_from_stage_id(self, stage_id):
        request.env.cr.execute("""
            SELECT
                imd.res_id AS id,
                CONCAT(imd.module, '.', imd.name) AS xmlid
            FROM
                ir_model_data imd
            WHERE
                imd.model = 'ike.service.stage'
                AND imd.res_id = %(stage_id)s
            LIMIT 1;
        """, {'stage_id': stage_id})
        return request.env.cr.dictfetchone()

    def _ike_get_ike_event_supplier_elapsed_times(self, event_id, vehicle_id):
        select_progress_state, inner_progress_state = self._ike_get_auxiliary_query_for_progress_state()
        query = """
            SELECT
                {select_progress_state},
                supplier.elapsed_seconds,
                supplier.app_timestamp
            FROM ike_event_supplier_elapsed_time supplier
            INNER JOIN fleet_vehicle vehicle ON vehicle.id = supplier.vehicle_id
            {inner_progress_state}
            WHERE
                supplier.event_id = %(event_id)s
                AND vehicle.x_vehicle_ref = %(vehicle_id)s
            ORDER BY supplier.create_date DESC;
        """.format(
            select_progress_state=select_progress_state,
            inner_progress_state=inner_progress_state
        )
        request.env.cr.execute(query, {'event_id': event_id, 'vehicle_id': vehicle_id})
        return request.env.cr.dictfetchall()

    # ============================= #
    #         CATALOG/EVENT         #
    # ============================= #
    @http.route('/ike/catalog/events/get', type='json', auth='user', methods=['POST'])
    def ike_catalog_events_get(self, **kw):
        # ToDo: elapsed_seconds & app_timestamp
        vehicle_id = kw.get('vehicle_id', False)

        if not vehicle_id:
            return BadRequest(_('Missing parameters'))
        vehicle_id = str(vehicle_id)

        # Obtener la zona horaria del usuario actual
        user_tz = request.env.user.tz or 'UTC'
        user_lang = request.env.user.lang or 'en_US'

        select_progress_state, inner_progress_state = self._ike_get_auxiliary_query_for_progress_state()
        query = """
            WITH events_data AS (
                SELECT
                    ievent.id,
                    ievent.name,
                    (ievent.event_date AT TIME ZONE 'UTC') AT TIME ZONE %(user_tz)s AS event_date,
                    ievent.step_number,
                    ies.ref AS stage_ref,
                    ievent.user_code,
                    {select_progress_state},
                    service.name AS service,
                    COALESCE(subservice.name->>%(user_lang)s, subservice.name->>'en_US') AS subservice,
                    ievent.destination_latitude AS latitude,
                    ievent.destination_longitude AS longitude,
                    ievent.destination_label AS destination,
                    pp.x_min_required_photos AS min_required_photos
                FROM ike_event ievent
                INNER JOIN product_category service ON service.id = ievent.service_id
                INNER JOIN product_product pp ON pp.id = ievent.sub_service_id
                INNER JOIN product_template subservice ON subservice.id = pp.product_tmpl_id
                INNER JOIN ike_event_stage ies ON ies.id = ievent.stage_id
                LEFT JOIN ike_event_supplier supplier ON ievent.id = supplier.event_id
                LEFT JOIN fleet_vehicle vehicle ON vehicle.id = supplier.truck_id
                {inner_progress_state}
                WHERE
                    supplier.selected = true
                    AND ies.ref IN ('assigned', 'in_progress')
                    AND supplier.state = 'assigned'
                    AND supplier.notification_sent_to_app = true
                    AND vehicle.x_vehicle_ref = %(vehicle_id)s
            )
            SELECT * FROM events_data
            -- Excluimos etapas no mapeadas
            WHERE progress_state NOT IN ('-1', '6')
            ORDER BY event_date DESC;
        """.format(
            select_progress_state=select_progress_state,
            inner_progress_state=inner_progress_state
        )
        request.env.cr.execute(query, {'user_tz': user_tz, 'vehicle_id': vehicle_id, 'user_lang': user_lang})
        events = request.env.cr.dictfetchall()
        for event in events:
            event['destination'] = html2plaintext(event['destination'] or '')  # Quitar salto HTML
        return events

    @http.route('/ike/catalog/events/get/olds', type='json', auth='user', methods=['POST'])
    def ike_catalog_events_get_olds(self, **kw):
        vehicle_id = kw.get('vehicle_id', False)
        if not vehicle_id:
            return BadRequest(_('Missing parameters'))
        vehicle_id = str(vehicle_id)

        # ToDo: elapsed_seconds & app_timestamp
        user_tz = request.env.user.tz or 'UTC'
        user_lang = request.env.user.lang or 'en_US'

        select_progress_state, inner_progress_state = self._ike_get_auxiliary_query_for_progress_state()
        query = """
            WITH events_data AS (
                SELECT
                    ievent.id,
                    ievent.name,
                    (ievent.event_date AT TIME ZONE 'UTC') AT TIME ZONE %(user_tz)s AS event_date,
                    ievent.step_number,
                    ies.ref AS stage_ref,
                    ievent.user_code,
                    {select_progress_state},
                    service.name AS service,
                    COALESCE(subservice.name->>%(user_lang)s, subservice.name->>'en_US', '') AS subservice,
                    ievent.destination_latitude AS latitude,
                    ievent.destination_longitude AS longitude,
                    ievent.destination_label AS destination,
                    pp.x_min_required_photos AS min_required_photos
                FROM ike_event ievent
                INNER JOIN product_category service ON service.id = ievent.service_id
                INNER JOIN product_product pp ON pp.id = ievent.sub_service_id
                INNER JOIN product_template subservice ON subservice.id = pp.product_tmpl_id
                INNER JOIN ike_event_stage ies ON ies.id = ievent.stage_id
                LEFT JOIN ike_event_supplier supplier ON ievent.id = supplier.event_id
                LEFT JOIN fleet_vehicle vehicle ON vehicle.id = supplier.truck_id
                {inner_progress_state}
                WHERE
                    supplier.selected = true
                    AND ies.ref = 'completed'
                    AND supplier.state = 'assigned'
                    AND supplier.notification_sent_to_app = true
                    AND vehicle.x_vehicle_ref = %(vehicle_id)s
            )
            SELECT * FROM events_data
            -- Excluimos etapas no mapeadas
            WHERE progress_state != '-1'
            ORDER BY event_date DESC
            LIMIT 5;
        """.format(
            select_progress_state=select_progress_state,
            inner_progress_state=inner_progress_state
        )
        request.env.cr.execute(query, {'user_tz': user_tz, 'vehicle_id': vehicle_id, 'user_lang': user_lang})
        events = request.env.cr.dictfetchall()
        for event in events:
            event['destination'] = html2plaintext(event['destination'] or '')  # Quitar salto HTML
        return events

    @http.route('/ike/catalog/events/get/last', type='json', auth='user', methods=['POST'])
    def ike_catalog_events_get_last(self, **kw):
        vehicle_id = kw.get('vehicle_id', False)
        if not vehicle_id:
            return BadRequest(_('Missing parameters'))
        vehicle_id = str(vehicle_id)

        # ToDo: elapsed_seconds & app_timestamp
        user_tz = request.env.user.tz or 'UTC'
        user_lang = request.env.user.lang or 'en_US'
        select_progress_state, inner_progress_state = self._ike_get_auxiliary_query_for_progress_state()
        query = """
            WITH events_data AS (
                SELECT
                    ievent.id,
                    ievent.name,
                    (ievent.event_date AT TIME ZONE 'UTC') AT TIME ZONE %(user_tz)s AS event_date,
                    ievent.step_number,
                    ies.ref AS stage_ref,
                    ievent.user_code,
                    {select_progress_state},
                    service.name AS service,
                    COALESCE(subservice.name->>%(user_lang)s, subservice.name->>'en_US', '') AS subservice,
                    ievent.destination_latitude AS latitude,
                    ievent.destination_longitude AS longitude,
                    ievent.destination_label AS destination,
                    pp.x_min_required_photos AS min_required_photos
                FROM ike_event ievent
                INNER JOIN product_category service ON service.id = ievent.service_id
                INNER JOIN product_product pp ON pp.id = ievent.sub_service_id
                INNER JOIN product_template subservice ON subservice.id = pp.product_tmpl_id
                INNER JOIN ike_event_stage ies ON ies.id = ievent.stage_id
                LEFT JOIN ike_event_supplier supplier ON ievent.id = supplier.event_id
                LEFT JOIN fleet_vehicle vehicle ON vehicle.id = supplier.truck_id
                {inner_progress_state}
                WHERE
                    supplier.selected = true
                    AND ies.ref = 'in_progress'
                    AND supplier.state = 'assigned'
                    AND supplier.notification_sent_to_app = true
                    AND vehicle.x_vehicle_ref = %(vehicle_id)s
            )
            SELECT * FROM events_data
            -- Excluimos etapas no mapeadas, asignado y finalizado
            WHERE progress_state NOT IN ('-1', '0', '6')
            ORDER BY event_date DESC
            LIMIT 1;
        """.format(
            select_progress_state=select_progress_state,
            inner_progress_state=inner_progress_state
        )
        request.env.cr.execute(query, {'user_tz': user_tz, 'vehicle_id': vehicle_id, 'user_lang': user_lang})
        events = request.env.cr.dictfetchall()
        for event in events:
            event['destination'] = html2plaintext(event['destination'] or '')  # Quitar salto HTML
            # Array de los tiempos en que se cambió de etapa hasta el momento
            elapsed_times = self._ike_get_ike_event_supplier_elapsed_times(event['id'], vehicle_id)
            event['elapsed_times'] = elapsed_times if elapsed_times else []

        return events

    @http.route('/ike/catalog/events/set/progress_state', type='json', auth='user', methods=['POST'])
    def ike_catalog_events_set_progress_state(self, **kw):
        vehicle_id = kw.get('vehicle_id', False)
        try:
            event_id = int(kw.get('event_id', 0))
        except (TypeError, ValueError):
            raise BadRequest(_('Invalid parameters'))

        try:
            progress_state = str(int(kw.get('progress_state', '')))  # normaliza a str numérico
        except (TypeError, ValueError):
            raise BadRequest(_('Invalid progress_state'))
        if progress_state not in PROGRESS_STATES_MAP_STAGE:
            raise BadRequest(_('Invalid progress_state value'))

        app_timestamp = kw.get('app_timestamp', False)
        elapsed_seconds = kw.get('elapsed_seconds', 0)
        latitude = kw.get('latitude', '')
        longitude = kw.get('longitude', '')

        _logger.warning(f"/set/progress_state/{event_id}/{vehicle_id}/{progress_state}")

        if not event_id or progress_state == '' or not vehicle_id:
            raise BadRequest(_('Missing parameters'))
        vehicle_id = str(vehicle_id)

        ike_event_supplier_id = False

        try:
            # Obtener el supplier line id primero
            ike_event_supplier_id = self._ike_event_supplier_line_id(event_id, vehicle_id)
            if not ike_event_supplier_id:
                return {'status': 'error', 'message': 'Supplier line not found or cancelled'}

            # Obtener el xmlid del stage actual del supplier
            request.env.cr.execute("""
                SELECT
                    stage.ref AS event_stage_ref,
                    CONCAT(imd.module, '.', imd.name) AS supplier_stage_xmlid
                FROM
                    ike_event_supplier supplier
                INNER JOIN
                    ike_event ie ON supplier.event_id = ie.id
                LEFT JOIN
                    ike_event_stage stage ON ie.stage_id = stage.id
                LEFT JOIN
                    ir_model_data imd
                        ON supplier.stage_id = imd.res_id
                        AND imd.model = 'ike.service.stage'
                WHERE
                    supplier.id = %(line_id)s;
            """, {'line_id': ike_event_supplier_id['id']})

            result = request.env.cr.dictfetchone()

            if not result:
                raise BadRequest(_('Supplier stage not found'))

            if result:
                current_xmlid = result['supplier_stage_xmlid']
                event_stage_ref = result['event_stage_ref']

                # Validación 1: No permitir retroceder el progress_state
                if current_xmlid and current_xmlid in PROGRESS_STATES_MAP_REVERSE:
                    current_state = int(PROGRESS_STATES_MAP_REVERSE[current_xmlid])
                    new_state = int(progress_state)

                    if new_state < current_state:
                        raise BadRequest(_('Cannot set a lower progress_state than current'))

                # Validación 2: Si ref no es 'searching' o 'in_progress',
                # no permitir progress_state 0
                if progress_state == '0' and event_stage_ref not in ['searching', 'in_progress']:
                    raise BadRequest(_('Cannot set progress_state 0 when event stage is not searching or in_progress'))

            # Obtener el xmlid y res_id del stage a asignar
            xmlid = PROGRESS_STATES_MAP_STAGE.get(str(progress_state), False)
            if xmlid:
                res_id = request.env.ref(xmlid).id

                # Actualizar/Crear registro de tiempo
                if app_timestamp and elapsed_seconds:
                    vehicle_query = """
                        SELECT id
                        FROM fleet_vehicle
                        WHERE x_vehicle_ref = %s
                    """
                    request.env.cr.execute(vehicle_query, (vehicle_id,))
                    vehicle_id_int = request.env.cr.fetchone()
                    if vehicle_id_int:
                        request.env['ike.event.supplier.elapsed_time'].create({
                            'event_id': event_id,
                            'vehicle_id': vehicle_id_int[0],
                            'stage_id': res_id,
                            'app_timestamp': app_timestamp,
                            'elapsed_seconds': elapsed_seconds,
                            'latitude': latitude,
                            'longitude': longitude,
                        })

                # Actualizar el supplier
                supplier = request.env['ike.event.supplier'].sudo().browse(ike_event_supplier_id['id'])
                supplier.action_from_progress_state(progress_state)
                # Detonar bus.bus para actualizar vista
                if ike_event_supplier_id:
                    line_supplier_id = ike_event_supplier_id['id']
                    _logger.warning("Enviando bus.bus")
                    request.env['bus.bus']._sendone(
                        target=f'custom_ike_event_supplier_stages_{line_supplier_id}',
                        notification_type='update_ike_event_supplier_stage',
                        message={
                            'id': line_supplier_id
                        }
                    )

        except BadRequest as e:
            _logger.warning(str(e))
            raise BadRequest(e)
        except Exception as e:
            _logger.warning(str(e))
            raise InternalServerError(e)

        return {'status': 'success', 'progress_state': progress_state}

    @http.route('/ike/catalog/events/get/info', type='json', auth='user', methods=['POST'])
    def ike_catalog_events_get_info(self, **kw):
        event_id = kw.get('event_id', False)
        vehicle_id = kw.get('vehicle_id', False)
        if not event_id or not vehicle_id:
            raise BadRequest(_('Missing parameters'))
        vehicle_id = str(vehicle_id)

        event = request.env['ike.event'].sudo().browse([event_id])
        event_sudo = event.sudo()

        if not event_sudo:
            raise NotFound(_('Event not found'))

        service = request.env[event_sudo.service_res_model].sudo().browse([event_sudo.service_res_id])
        service_sudo = service.sudo()

        survey = event_sudo.sub_service_survey_input_id
        survey_sudo = survey.sudo()

        supplier_line = self._ike_event_supplier_line_id(event_id, vehicle_id)
        if not supplier_line:
            raise NotFound(_('Supplier line not found'))

        supplier_xmlid = self._get_xmlid_from_stage_id(supplier_line['stage_id'])
        supplier_progress_state = PROGRESS_STATES_MAP_REVERSE.get(supplier_xmlid['xmlid'], "-1")

        response = {
            'id': event_sudo.id,
            'name': event_sudo.name,
            'service': event_sudo.service_id.name,
            'subservice': event_sudo.sub_service_id.name,
            'event_date': fields.Datetime.context_timestamp(event_sudo, event_sudo.event_date).strftime('%Y-%m-%d %H:%M:%S'),
            'step_number': event_sudo.step_number,
            'stage_ref': event_sudo.stage_id.ref,
            'user_code': event_sudo.user_code,
            'progress_state': supplier_progress_state,
            'origin': None,
            'destination': None,
            'min_required_photos': 0,
            'vehicle': {},
            'questions': [],
            'elapsed_times': [],
        }

        # Origin
        if event_sudo.location_latitude and event_sudo.location_longitude:
            response['origin'] = {
                'latitude': event_sudo.location_latitude,
                'longitude': event_sudo.location_longitude,
                'label': html2plaintext(event_sudo.location_label),  # Quitar salto HTML
            }

        # Destination
        if event_sudo.destination_latitude and event_sudo.destination_longitude:
            response['destination'] = {
                'latitude': event_sudo.destination_latitude,
                'longitude': event_sudo.destination_longitude,
                'label': html2plaintext(event_sudo.destination_label),  # Quitar salto HTML
            }

        # Min required photos
        if event_sudo.sub_service_id:
            response['min_required_photos'] = event_sudo.sub_service_id.x_min_required_photos

        # Service
        if event_sudo.service_res_model == 'ike.service.input.vial':
            # base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            response['vehicle'] = {
                'vehicle_brand': service_sudo.vehicle_brand,
                'vehicle_model': service_sudo.vehicle_model,
                'vehicle_year': service_sudo.vehicle_year,
                'vehicle_category_id': service_sudo.vehicle_category_id.id if service_sudo.vehicle_category_id else False,
                'vehicle_plate': service_sudo.vehicle_plate,
                'vehicle_color': service_sudo.vehicle_color,
                # 'vehicle_plate_image': f'{base_url}/web/image/ike.service.input.vial/{service_sudo.id}/vehicle_plate_image'
            }

        # Questions
        user_lang = request.env.user.lang
        survey_translated = survey_sudo.with_context(lang=user_lang)
        if survey_sudo:
            response['questions'] = [
                {
                    'title': x.question_id.title,
                    'question': html2plaintext(x.question_id.description),
                    'answer': x.display_name,
                } for x in survey_translated.user_input_line_ids if x.question_id.x_send_to_operator
            ]

        # Array de los tiempos en que se cambió de etapa hasta el momento
        elapsed_times = self._ike_get_ike_event_supplier_elapsed_times(event_id, vehicle_id)
        response['elapsed_times'] = elapsed_times if elapsed_times else []

        return response

    @http.route('/ike/catalog/events/get/report', type='json', auth='user', methods=['POST'])
    def ike_catalog_events_get_report(self, **kw):
        # ToDo: elapsed_seconds & app_timestamp
        event_id = kw.get('event_id', False)
        if not event_id:
            raise BadRequest(_('Missing parameters'))

        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
        user_tz = request.env.user.tz or 'UTC'

        request.env.cr.execute("""
            SELECT
                ee.event_id AS id,
                MAX(ie.name) AS name,
                MAX((ie.event_date AT TIME ZONE 'UTC') AT TIME ZONE %(user_tz)s) AS event_date,
                CONCAT(MAX(%(base_url)s), '/web/image/ike.event.evidence/', ee.id, '/nu_user_sign') AS sign,
                CASE
                    WHEN ee.comments IS NOT NULL THEN
                        ee.comments
                    ELSE ''
                END AS comments,
                CASE
                    WHEN ee.extra_pay IS NOT NULL THEN
                        ee.extra_pay
                    ELSE false
                END AS extra_pay,
                CASE
                    WHEN ee.extra_pay_amount IS NOT NULL THEN
                        ee.extra_pay_amount
                    ELSE 0
                END AS extra_pay_amount,
                ee.id AS evidence_id,
                ee.evidence_type,
                (ee.create_date AT TIME ZONE 'UTC') AT TIME ZONE %(user_tz)s AS evidence_date ,
                jsonb_agg(
                    jsonb_build_object(
                        'id', eed.id,
                        'side', eed.side,
                        'image', CONCAT(%(base_url)s, '/web/image/ike.event.evidence.detail/', eed.id, '/file_image')
                    ) ORDER BY eed.id ASC
                ) as evidence_images
            FROM ike_event ie
            JOIN ike_event_evidence ee ON ee.event_id = ie.id
            JOIN ike_event_evidence_detail eed ON eed.event_evidence_id = ee.id
            WHERE ee.event_id = %(event_id)s
            GROUP BY ee.id;
        """, {'base_url': base_url, 'user_tz': user_tz, 'event_id': event_id})
        grouped_evidences = request.env.cr.dictfetchall()
        if not grouped_evidences:
            raise NotFound(_('Evidence not found'))

        return grouped_evidences

    # =============================== #
    #         CATALOG/VEHICLE         #
    # =============================== #
    @http.route('/ike/catalog/vehicles/get', type='json', auth='user', methods=['POST'])
    def ike_catalog_vehicles_get(self, **kw):
        # Obtener contacto del usuario
        partner_id = request.env.user.partner_id
        # Determinar si el ususario es chofer
        #   Si no es chofer, devolver lista vacía
        # Obtener el proveedor de la tabla de realción del conductor con el proveedor
        request.env.cr.execute("""
            SELECT supplier_id AS id
            FROM res_partner_supplier_users_rel
            WHERE partner_id = %s;
        """ % (partner_id.id,))

        supplier_id = request.env.cr.fetchone()
        #   Si no existe relación, devolver lista vacía
        if not supplier_id:
            raise NotFound(_("Supplier not found"))

        supplier_id = supplier_id[0]
        # Buscar todos los vehículos de ese proveedor
        request.env.cr.execute(self._ike_get_query_for_supplier_vehicles(supplier_id))
        supplier_vehicles = request.env.cr.dictfetchall()

        # Obtener la url base
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')

        all_vehicles = []
        user_vehicles = []
        for vehicle in supplier_vehicles:
            if len(user_vehicles) == 0:
                all_vehicles.append(self._prepare_ike_vehicle_data_response(base_url, vehicle))
            if vehicle['driver_id'] == partner_id.id:
                user_vehicles.append(self._prepare_ike_vehicle_data_response(base_url, vehicle))

        # Devolver los vehículos
        return {
            'vehicles': user_vehicles if user_vehicles else all_vehicles,
            'status': 'success'
        }

    @http.route('/ike/catalog/vehicles/set', type='json', auth='user', methods=['POST'])
    def ike_catalog_vehicles_set(self, **kw):
        return {'status': 'Not implemented yet'}

    @http.route('/ike/catalog/vehicle/set_location', type='json', auth='user', methods=['POST'])
    def ike_catalog_vehicle_set_location(self, **kw):
        channel = kw.get('channel', 'CUSTOM_MAP_TRUCK_MONITOR')
        vehicle_id = kw.get('vehicle_id', False)
        state = kw.get('state', False)
        latitude = kw.get('latitude', False)
        longitude = kw.get('longitude', False)

        if not vehicle_id or not latitude or not longitude:
            _logger.warning(f'Batched Location: {vehicle_id}/{state}/{latitude}/{longitude}')
            return BadRequest(_("Missing parameters"))
        vehicle_id = str(vehicle_id)

        # if state not in ['available', 'not_available', 'in_service', 'disabled']:
        #     raise BadRequest(_('Invalid state'))

        try:
            vehicle_location_batcher.add_location(
                channel,
                vehicle_id,
                state,
                latitude,
                longitude,
                db_name=request.db,
                user_id=request.session.uid,
            )
            _logger.info(f'Batched Location: {vehicle_id}/{state}/{latitude}/{longitude}')
            return {
                'status': 'success',
                'message': _('Location batched'),
                'queued': True
            }
        except Exception as e:
            raise InternalServerError(str(e))

    @http.route('/ike/catalog/vehicle/set/state', type='json', auth='user', methods=['POST'])
    def ike_catalog_vehicle_set_state(self, **kw):
        vehicle_id = kw.get('vehicle_id', False)
        state = kw.get('state', False)
        external_supplier = kw.get('external_supplier', False)

        if not vehicle_id or not state:
            return BadRequest(_("Missing parameters"))
        vehicle_id = str(vehicle_id)

        # Validar que sea un estado válido
        if state not in ['available', 'not_available', 'in_service', 'disabled', 'logout']:
            raise NotFound(_('Invalid state'))

        # Obtener objeto del vehículo
        vehicle = request.env['fleet.vehicle'].sudo().search([('x_vehicle_ref', '=', vehicle_id)], limit=1)
        vehicle_sudo = vehicle.sudo()
        if not vehicle_sudo:
            raise NotFound(_('Vehicle not found'))

        if not external_supplier:
            # Validar que el vehículo no esté asignado a otro usuario
            if vehicle_sudo.driver_id and vehicle_sudo.driver_id.id != request.env.user.partner_id.id:
                raise Forbidden(_('Vehicle is assigned to another user'))

            # Validar que el usuario actual, sea un conductor del proveedor al que pertenece el vehículo recibido
            request.env.cr.execute("""
                SELECT supplier_id AS id
                FROM res_partner_supplier_users_rel
                WHERE partner_id = %s;
            """ % (request.env.user.partner_id.id,))

            supplier_id = request.env.cr.fetchone()
            if not supplier_id:
                raise Forbidden(_('User is not a conductor of the supplier'))
            supplier_id = supplier_id[0]
            if vehicle_sudo.x_partner_id.id != supplier_id:
                raise Forbidden(_('Vehicle is not assigned to the current supplier'))

        # 'available', - Ya hizo checkin
        # 'not_available', - La grua no está habilitada, no está laborando
        # 'in_service', - Al iniciar un servicio, al finalizar regresaría a 'available'
        # 'disabled' - Estado desconocido (mantenimiento o alguna otra situación)
        # 'logout' - El usuario ha cerrado sesión

        driver = False
        driver_change = False
        new_data = {'x_vehicle_service_state': state}
        if state in ('available', 'not_available', 'in_service'):
            driver_change = vehicle_sudo.driver_id.id != request.env.user.partner_id.id
            driver = request.env.user.partner_id.id
        elif state == 'disabled':
            driver_change = vehicle_sudo.driver_id
            driver = False
        elif state == 'logout':
            new_data['x_vehicle_service_state'] = 'not_available'
            driver_change = True
            driver = False

        if not external_supplier:
            if driver_change:
                vehicles_assigned = request.env['fleet.vehicle'].sudo().search_count([
                    ('driver_id', '=', request.env.user.partner_id.id)
                ])
                if vehicles_assigned > 0:
                    raise Forbidden(_('User is assigned to other vehicles'))
                new_data['driver_id'] = driver

        vehicle_sudo.write(new_data)

        return {'success': True}

    # ============================== #
    #         CATALOG/DRIVER         #
    # ============================== #
    @http.route('/ike/catalog/drivers/set', type='json', auth='user', methods=['POST'])
    def ike_catalog_drivers_set(self, **kw):
        return {'status': 'Not implemented yet'}

    # ============================== #
    #    CATALOG/CANCEL_REASONS      #
    # ============================== #
    @http.route('/ike/catalog/cancel_reasons', type='json', auth='user', methods=['GET'])
    def ike_catalog_cancel_reasons_get(self, **kw):
        if not request.env.uid:
            request.env.cr.rollback()
            raise Unauthorized('Usuario no autenticado')
        reasons = request.env['ike.event.cancellation.reason'].search_read([('show_supplier', '=', True)], ['id', 'name'])
        return reasons

    # ========================== #
    #      EVENT/CONCEPTS        #
    # ========================== #
    @http.route(
        '/ike/catalog/additional_concepts', type='json', auth='user', methods=['GET']
    )
    def ike_catalog_additional_concepts_get(self, **kw):
        """
        Retorna el catalogo de conceptos adicionales disponibles para asignar a eventos.

        Usa SQL directo en lugar del ORM de Odoo por razones de rendimiento:
        la traduccion del nombre del producto y la UOM requieren acceder al campo
        JSONB de traducciones (name ->> lang), lo cual es verbose con el ORM
        pero trivial en SQL. Ademas evita multiples queries que el ORM generaria
        para resolver los campos relacionados.

        El dominio base se obtiene de product.product.get_concepts_domain(), que
        centraliza los criterios generales de un "concepto" en el sistema IKE.
        A ese dominio se le agrega el filtro x_additional_ok = True para restringir
        solo a los conceptos marcados como disponibles para asignacion adicional.

        La traduccion de nombre y UOM usa COALESCE para caer al idioma 'en_US'
        si no existe traduccion en el idioma del usuario, evitando nulls en la respuesta.

        Returns:
            list[dict]: Lista de conceptos, cada uno con la forma:
                {
                    "id": <product.product id>,
                    "name": "<nombre traducido al idioma del usuario>",
                    "uom_id": [<uom.uom id>, "<nombre de unidad de medida traducido>"]
                }

        Raises:
            Unauthorized: Si el usuario no tiene sesion activa.
        """
        if not request.env.uid:
            request.env.cr.rollback()
            raise Unauthorized('Usuario no autenticado')

        # Construimos el dominio desde el metodo centralizado del modelo,
        # evitando duplicar criterios de filtrado en multiples lugares.
        Concept = request.env['product.product']
        concepts_domain = Concept.get_concepts_domain()

        # x_additional_ok es un campo custom que marca los productos
        # habilitados especificamente para ser asignados como conceptos adicionales.
        concepts_domain.append(('x_additional_ok', '=', True))

        # _where_calc traduce el dominio de Odoo a un objeto Query con
        # from_clause y where_clause listos para embeber en SQL raw,
        # respetando los permisos de acceso (ir.rule) del usuario.
        query = Concept._where_calc(concepts_domain)

        # Idioma del usuario para resolver la traduccion de campos JSONB.
        # Fallback a 'en_US' si el usuario no tiene idioma configurado.
        lang = request.env.user.lang or 'en_US'

        request.env.cr.execute(
            SQL(
                """
                SELECT
                    product_product.id AS id,

                    -- Nombre del producto traducido al idioma del usuario.
                    -- COALESCE garantiza que nunca retorne null:
                    -- intenta con el idioma del usuario, luego en_US, luego string vacio.
                    COALESCE(
                        product_template.name ->> %(lang)s,
                        product_template.name ->> 'en_US',
                        ''
                    ) AS name,

                    -- UOM como array [id, nombre] para que el cliente no necesite
                    -- un endpoint adicional para resolver la unidad de medida.
                    json_build_array(
                        uom.id,
                        COALESCE(
                            uom.name ->> %(lang)s,
                            uom.name ->> 'en_US',
                            ''
                        )
                    ) AS uom_id

                FROM %(from_clause)s
                INNER JOIN product_template ON product_template.id = product_product.product_tmpl_id
                INNER JOIN uom_uom uom ON uom.id = product_template.uom_id
                WHERE %(where_clause)s
                    -- Excluimos explicitamente productos archivados,
                    -- aunque el dominio de Odoo normalmente ya lo filtra.
                    AND product_product.active = true
                ORDER BY product_product.id ASC
                """,
                from_clause=query.from_clause,
                where_clause=query.where_clause or SQL("TRUE"),
                lang=lang,
            )
        )

        # dictfetchall retorna todas las filas como lista de dicts,
        # que Odoo serializa directamente a JSON en la respuesta.
        return request.env.cr.dictfetchall()
