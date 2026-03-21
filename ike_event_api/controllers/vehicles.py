import threading
import time
# from datetime import datetime, timezone
import odoo
from odoo import http  # , api, SUPERUSER_ID
from odoo.http import request
from collections import defaultdict, deque
from werkzeug.exceptions import (Forbidden, NotFound, BadRequest, InternalServerError)  # type: ignore
import logging

_logger = logging.getLogger(__name__)

# ! IMPORTANT !
# 25/21/10
# Este archivo quedará sin uso en aproximadamente 1 mes, después del último release de la APP movil
# La funcionalidad actualiazda y correcta con los endpoints definidos en sesión de usuario son los
# que se encuentran en el archivo 'catalogs.py'
# Se mantiene esta versión en lo que dura el release anterior de la APP movil para evitar errores.

class LocationBatcher:
    """
    Singleton to manage batching
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(LocationBatcher, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.location_batches = defaultdict(deque)  # {channel: deque of locations}
        self.batch_locks = defaultdict(threading.Lock)  # {channel: lock}
        self.batch_size = 50
        self.batch_timeout = 10  # seconds
        self.last_send_time = defaultdict(float)  # {channel: timestamp}
        self.timer_threads = {}  # {channel: timer_thread}
        self.db_name = None
        self.user_id = None

    def add_location(self, channel, vehicle_id, state, latitude, longitude, db_name=None, user_id=None):
        if db_name:
            self.db_name = db_name
        if user_id:
            self.user_id = user_id

        with self.batch_locks[channel]:
            location_data = {
                'vehicle_id': vehicle_id,
                'state': state,
                'latitude': latitude,
                'longitude': longitude,
                'timestamp': time.time()
            }

            self.location_batches[channel].append(location_data)

            if len(self.location_batches[channel]) >= self.batch_size:
                self._send_batch(channel)
                self._cancel_timer(channel)
            else:
                if channel not in self.timer_threads or not self.timer_threads[channel].is_alive():
                    self._start_timer(channel)

    def _start_timer(self, channel):
        """"""
        def send_after_timeout():
            time.sleep(self.batch_timeout)
            with self.batch_locks[channel]:
                if self.location_batches[channel]:
                    self._send_batch(channel)

        timer_thread = threading.Thread(target=send_after_timeout, daemon=True)
        timer_thread.start()
        self.timer_threads[channel] = timer_thread

    def _cancel_timer(self, channel):
        """"""
        if channel in self.timer_threads and self.timer_threads[channel].is_alive():
            pass

    def _send_batch(self, channel):
        """"""
        if not self.location_batches[channel]:
            return

        locations = []
        while self.location_batches[channel]:
            locations.append(self.location_batches[channel].popleft())

        if locations and self.db_name:
            try:
                db_registry = odoo.modules.registry.Registry(self.db_name)
                with db_registry.cursor() as cr:
                    # UPSERT
                    values = [
                        (
                            d['vehicle_id'],
                            d['state'],
                            str(d['latitude']),
                            str(d['longitude']),
                        )
                        for d in locations
                    ]

                    query = """
                        UPDATE fleet_vehicle
                        SET x_vehicle_service_state = data.state,
                            x_latitude = data.latitude,
                            x_longitude = data.longitude
                        FROM (VALUES %s) AS data(id, state, latitude, longitude)
                        WHERE fleet_vehicle.id = data.id
                    """

                    cr.execute_values(query, values)

            except Exception as e:
                print("ERROR:", str(e))
                for location in reversed(locations):
                    self.location_batches[channel].appendleft(location)


location_batcher = LocationBatcher()


class VehiclesAPIController(http.Controller):

    def _ike_get_query_for_supplier_vehicles(self, supplier_id):
        return """
            SELECT
                fv.id
                ,fv.name
                ,rps.id AS supplier_id
                ,rps.name AS supplier_name
                ,rp.id AS driver_id
                ,rp.name AS driver_name
                ,fv.brand_id
                ,fvmb.name AS brand_name
                ,fv.model_id
                ,fvm.name AS model_name
                ,fv.license_plate
                ,fv.x_vehicle_service_state
                ,fvmb_img.store_fname AS brand_image_store
                ,fvmb_img.mimetype AS brand_image_type
            FROM
                fleet_vehicle fv
            LEFT JOIN res_partner rp ON fv.driver_id = rp.id
            LEFT JOIN res_partner rps ON fv.x_partner_id = rps.id
            LEFT JOIN fleet_vehicle_model fvm ON fv.model_id = fvm.id
            LEFT JOIN fleet_vehicle_model_brand fvmb ON fvm.brand_id = fvmb.id
            LEFT JOIN ir_attachment fvmb_img ON fvmb_img.res_model = 'fleet.vehicle.model.brand'
                AND fvmb_img.res_id = fvmb.id
                AND fvmb_img.res_field = 'image_128'
                AND fvmb_img.type = 'binary'
            WHERE fv.x_partner_id = %s
                AND (fv.x_vehicle_service_state IS NULL
                OR fv.x_vehicle_service_state != 'disabled');
        """ % (supplier_id,)

    @http.route('/ike/send_vehicle_location', type='json', auth='user')
    def ike_send_vehicle_location(self, **kw):
        """"""
        try:
            channel = kw.get('channel', 'CUSTOM_MAP_TRUCK_MONITOR')
            vehicle_id = kw['vehicle_id']
            state = kw['state']
            latitude = kw['latitude']
            longitude = kw['longitude']

            # if state not in ['available', 'not_available', 'in_service', 'disabled']:
            #     raise BadRequest('Invalid state')

            location_batcher.add_location(
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
                'message': 'Location batched',
                'queued': True
            }
        except Exception as e:
            raise InternalServerError(str(e))

    @http.route('/ike/vehicles', type='json', auth='user')
    def ike_get_event_vehicles(self):
        empty_result = {'vehicles': [], 'status': 'error'}
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
            return empty_result

        supplier_id = supplier_id[0]
        # Buscar todos los vehículos de ese proveedor
        request.env.cr.execute(self._ike_get_query_for_supplier_vehicles(supplier_id))
        supplier_vehicles = request.env.cr.dictfetchall()

        # Obtener la url base
        base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')

        all_vehicles = []
        user_vehicles = []
        for v in supplier_vehicles:
            all_vehicles.append({
                'id': v['id'],
                'name': v['name'],
                'supplier_id': v['supplier_id'],
                'supplier_name': v['supplier_name'],
                'driver_id': v['driver_id'] or False,
                'driver_name': v['driver_name'] or False,
                'brand_id': v['brand_id'],
                'brand_name': v['brand_name'],
                'model_id': v['model_id'],
                'model_name': v['model_name'],
                'license_plate': v['license_plate'] or False,
                'service_state': v['x_vehicle_service_state'] or '',
                'image_128': "%s/web/image/fleet.vehicle/%s/image_128" % (base_url, v['id']),
            })
            if v['driver_id'] == partner_id.id:
                user_vehicles.append({
                    'id': v['id'],
                    'name': v['name'],
                    'supplier_id': v['supplier_id'],
                    'supplier_name': v['supplier_name'],
                    'driver_id': v['driver_id'],
                    'driver_name': v['driver_name'],
                    'brand_id': v['brand_id'],
                    'brand_name': v['brand_name'],
                    'model_id': v['model_id'],
                    'model_name': v['model_name'],
                    'license_plate': v['license_plate'],
                    'service_state': v['x_vehicle_service_state'] or '',
                    'image_128': "%s/web/image/fleet.vehicle/%s/image_128" % (base_url, v['id']),
                })

        # Devolver los vehículos
        return {
            'vehicles': user_vehicles if user_vehicles else all_vehicles,
            'status': 'success'
        }

    @http.route('/ike/vehicle/<int:vehicle_id>/state', type='json', auth='user')
    def ike_set_event_vehicle_state(self, vehicle_id, state, is_assigned=True):
        # Validar que sea un estado válido
        if state not in ['available', 'not_available', 'in_service', 'disabled', 'logout']:
            raise NotFound('Invalid state')

        # Obtener objeto del vehículo
        vehicle = request.env['fleet.vehicle'].sudo().browse([vehicle_id])
        vehicle_sudo = vehicle.sudo()
        if not vehicle_sudo:
            raise NotFound('Vehicle not found')

        # Validar que el vehículo no esté asignado a otro usuario
        if vehicle_sudo.driver_id and vehicle_sudo.driver_id.id != request.env.user.partner_id.id:
            raise Forbidden('Vehicle is assigned to another user')

        # Validar que el usuario actual, sea un conductor del proveedor al que pertenece el vehículo recibido
        request.env.cr.execute("""
            SELECT supplier_id AS id
            FROM res_partner_supplier_users_rel
            WHERE partner_id = %s;
        """ % (request.env.user.partner_id.id,))
        supplier_id = request.env.cr.fetchone()
        if not supplier_id:
            raise Forbidden('User is not a conductor of the supplier')
        supplier_id = supplier_id[0]
        if vehicle_sudo.x_partner_id.id != supplier_id:
            raise Forbidden('Vehicle is not assigned to the current supplier')

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

        if driver_change:
            new_data['driver_id'] = driver
        vehicle_sudo.write(new_data)

        return {'success': True}
