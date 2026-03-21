# -*- coding: utf-8 -*-

import threading
import time
from collections import defaultdict, deque

import odoo
import odoo.modules.registry
from odoo import api, SUPERUSER_ID, _


class IkeEventBatcher:
    """
    Singleton to manage batching
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(IkeEventBatcher, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.event_batches = defaultdict(deque)  # {channel: deque of locations}
        self.batch_locks = defaultdict(threading.Lock)  # {channel: lock}
        self.batch_size = 10
        self.last_send_time = defaultdict(float)  # {channel: timestamp}
        self.timer_threads = {}  # {channel: timer_thread}
        self.user_id = None

    def add_event_notification(self, db_name, channel, notification_type, data={}, batch_timeout=5):
        channel = f'{db_name}.{channel}.{notification_type}'
        with self.batch_locks[channel]:
            exist = False
            data_id = data.get('id')
            if data_id:
                for i, item in enumerate(self.event_batches[channel]):
                    if item['id'] == data_id:
                        self.event_batches[channel][i] = data
                        exist = True
                        break
            if not exist:
                self.event_batches[channel].append(data)
                if len(self.event_batches[channel]) >= self.batch_size:
                    self._send_batch(channel)
                    self._cancel_timer(channel)
                else:
                    if channel not in self.timer_threads or not self.timer_threads[channel].is_alive():
                        self._start_timer(channel, batch_timeout)

    def _start_timer(self, channel, batch_timeout):
        """"""
        def send_after_timeout():
            time.sleep(batch_timeout)
            with self.batch_locks[channel]:
                if self.event_batches[channel]:
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
        if not self.event_batches[channel]:
            return

        data = []
        while self.event_batches[channel]:
            data.append(self.event_batches[channel].popleft())

        if data:
            channel_aux = channel.split('.')
            db_name = channel_aux[0]
            channel_name = channel_aux[1]
            notification_type = channel_aux[2]
            try:
                db_registry = odoo.modules.registry.Registry(db_name)
                with db_registry.cursor() as cr:
                    uid = SUPERUSER_ID
                    env = api.Environment(cr, uid, {})

                    # BUS
                    batch_data = {
                        'data': data,
                        'count': len(data)
                    }

                    env['bus.bus']._sendone(
                        target=channel_name,
                        notification_type=notification_type,
                        message=batch_data,
                    )
                    print("SENDED:", len(data))
            except Exception as e:
                print("ERROR:", str(e))
                for item in reversed(data):
                    self.event_batches[channel].appendleft(item)


event_batcher = IkeEventBatcher()
