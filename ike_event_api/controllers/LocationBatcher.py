import threading
import time
import odoo
from collections import defaultdict, deque
from odoo import api, SUPERUSER_ID
import logging
_logger = logging.getLogger(__name__)


class VehicleLocationBatcher:
    """
    Singleton to manage batching
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(VehicleLocationBatcher, cls).__new__(cls)
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
                            str(d['latitude']),
                            str(d['longitude']),
                        )
                        for d in locations
                    ]

                    query = """
                        UPDATE fleet_vehicle
                        SET x_latitude = data.latitude,
                            x_longitude = data.longitude
                        FROM (VALUES %s) AS data(id, latitude, longitude)
                        WHERE fleet_vehicle.x_vehicle_ref = data.id
                    """

                    cr.execute_values(query, values)

                    # Notificar cambios a VideoWall
                    vehicle_ids = [v[0] for v in values]
                    env = api.Environment(cr, SUPERUSER_ID, {})
                    env['fleet.vehicle'].cron_push_location_updates(vehicle_ids=vehicle_ids)

            except Exception as e:
                print("ERROR:", str(e))
                for location in reversed(locations):
                    self.location_batches[channel].appendleft(location)
