# -*- coding: utf-8 -*-

from math import radians, sin, cos, sqrt, atan2

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

from .other_models.ike_event_batcher import event_batcher


class IkeEventSupplierSelection(models.Model):
    _inherit = 'ike.event.supplier'

    # === TIMER FIELDS === #
    priority = fields.Selection([
        ('0', 'None'),
        ('1', 'Low'),
        ('2', 'Normal'),
        ('3', 'High')
    ], default='0')
    notification_date = fields.Datetime(tracking=True, copy=False)
    acceptance_date = fields.Datetime(tracking=True, copy=False)
    acceptance_duration = fields.Float(help='Time it took to accept the service, in seconds.', copy=False)
    rejection_date = fields.Datetime(tracking=True, copy=False)
    assignation_date = fields.Datetime(string='Assigned (datetime)', tracking=True, copy=False)
    elapsed_time = fields.Integer(compute='_compute_elapsed_time')

    # === EXTRA FIELDS === #
    selected = fields.Boolean(default=False, copy=False)
    timer_duration = fields.Integer(help='Maximum timer duration, in seconds.', default=600, copy=False)
    is_manual = fields.Boolean(default=True)
    manual_notification = fields.Boolean(related='supplier_link_id.manual_notification')

    # === COMPUTES === #
    def _compute_elapsed_time(self):
        now = fields.Datetime.now()
        for rec in self:
            if not rec.notification_date:
                rec.elapsed_time = 0
                continue
            if rec.state == 'notified':
                rec.elapsed_time = max((now - rec.notification_date).total_seconds(), 0)
            elif rec.state in ['accepted', 'assigned']:
                rec.elapsed_time = max(((rec.acceptance_date or now) - rec.notification_date).total_seconds(), 0)
            elif rec.state in ['rejected', 'timeout', 'expired']:
                rec.elapsed_time = max(((rec.rejection_date or now) - rec.notification_date).total_seconds(), 0)
            else:
                rec.elapsed_time = 0

    # === ACTIONS === #
    def action_reset(self):
        self.write({
            'state': 'available',
            'selected': False,
            'notification_date': False,
            'acceptance_date': False,
            'rejection_date': False,
        })
        self.broadcastReload(reload_type='reset')

    def action_notify(self) -> list[int]:
        available_ids = self._lock_records_by_state('available')
        self_filtered = self.filtered(lambda x: x.id in available_ids)
        if not self_filtered:
            return []
        self_filtered.write({
            'state': 'notified',
            'notification_date': fields.Datetime.now(),
        })
        self_filtered.broadcastReload(reload_type='notify')

        return available_ids

    def action_accept(self) -> list[int]:
        notified_ids = self._lock_records_by_state('notified')
        available_ids = self._lock_records_by_state('available')
        self_filtered = self.filtered(
            lambda x: x.id in (notified_ids + available_ids)
            and (x.state == 'notified' or x.state == 'available' and x.is_manual)
        )
        if not self_filtered:
            return []
        self_filtered.write({
            'state': 'accepted',
            'acceptance_date': fields.Datetime.now(),
            'selected': True,
        })

        for rec in self_filtered:
            # if not rec.latitude or not rec.longitude:
            #     raise ValidationError(_('No latitude or longitude was assigned to the vehicle.'))
            # Folio
            rec.folio = self_filtered.env['ir.sequence'].next_by_code('ike.event.supplier')
            # Acceptance Duration
            difference = rec.acceptance_date - (rec.event_id.supplier_search_date or rec.acceptance_date)
            rec.acceptance_duration = int(difference.total_seconds())

        self_filtered._notify_expiration()
        # self_filtered.broadcastReload()

        # action_forward
        stage_searching = self.env.ref('ike_event.ike_event_stage_searching')
        stage_assigned = self.env.ref('ike_event.ike_event_stage_assigned')
        stage_in_progress = self.env.ref('ike_event.ike_event_stage_in_progress')
        event_ids = []
        for rec in self_filtered:
            use_action_forward = False
            if rec.event_id.id not in event_ids:
                event_ids.append(rec.event_id.id)
                if rec.event_id.stage_ref == stage_searching.ref and rec.event_id.step_number == 1:
                    # Searching
                    use_action_forward = True
                elif rec.event_id.stage_ref == stage_assigned.ref and rec.event_id.step_number == 3:
                    use_action_forward = True
                elif rec.event_id.stage_ref == stage_in_progress.ref and rec.event_id.step_number == 3:
                    use_action_forward = True
                if use_action_forward:
                    rec.event_id.sudo().with_context(dict(
                        current_stage_id=rec.event_id.stage_id.id,
                        current_step_number=rec.event_id.step_number,
                    )).action_forward()
            # Broadcast
            rec.broadcastReload(event_reload=use_action_forward, reload_type='forward')

        return self_filtered.ids

    def action_reject(self) -> list[int]:
        available_ids = self._lock_records_by_state('notified')
        self_filtered = self.filtered(lambda x: x.id in available_ids)
        if not self_filtered:
            return []
        self_filtered.write({
            'state': 'rejected',
            'rejection_date': fields.Datetime.now(),
        })
        self_filtered.broadcastReload(reload_type='reject')

        @self.env.cr.postcommit.add
        def send_broadcast_reject():
            if not self.env.context.get('not_notify_next'):
                with self.env.registry.cursor() as new_cr:
                    new_env = self.env(cr=new_cr)
                    records = self_filtered.with_env(new_env)
                    records._notify_next()

        return available_ids

    def action_timeout(self) -> list[int]:
        available_ids = self._lock_records_by_state('notified')
        self_filtered = self.filtered(lambda x: x.id in available_ids)
        if not self_filtered:
            return []
        self_filtered.write({
            'state': 'timeout',
            'rejection_date': fields.Datetime.now(),
        })
        self_filtered.broadcastReload(reload_type='timeout')

        @self.env.cr.postcommit.add
        def send_broadcast_timeout():
            if not self.env.context.get('not_notify_next'):
                with self.env.registry.cursor() as new_cr:
                    new_env = self.env(cr=new_cr)
                    records = self_filtered.with_env(new_env)
                    records._notify_next()

        return available_ids

    def action_expire(self) -> list[int]:
        available_ids = self._lock_records_by_state('notified')
        self_filtered = self.filtered(lambda x: x.id in available_ids)
        if not self_filtered:
            return []
        self_filtered.write({
            'state': 'expired',
            'rejection_date': fields.Datetime.now(),
        })
        self_filtered.broadcastReload(reload_type='expire')

        return available_ids

    def action_confirm_vehicle(self):
        """You can only confirm the vehicle if the service is assigned and event is scheduled."""
        accepted_ids = self._lock_records_by_state('accepted')
        assigned_ids = self._lock_records_by_state('assigned')
        self_filtered = self.filtered(
            lambda x: x.id in (accepted_ids + assigned_ids)
        )
        self_filtered.truck_id.x_vehicle_service_state = 'in_service'
        self_filtered.confirmed = True

        self_filtered.broadcastReload(reload_type='vehicle_confirmed')

    def action_notify_operator(self) -> list[int]:
        """App notification and Assign operation"""
        available_ids = self._lock_records_by_state('accepted')
        self_filtered = self.filtered(lambda x: x.id in available_ids)
        if not self_filtered:
            return []
        self_filtered.action_assign()
        # Hook: Mobile App Notification
        return available_ids

    def action_assign(self):
        accepted_ids = self._lock_records_by_state('accepted')
        assigned_ids = self._lock_records_by_state('assigned')
        self_filtered = self.filtered(
            lambda x: x.id in (accepted_ids + assigned_ids)
        )
        assigned_stage = self.env.ref('ike_event.ike_service_stage_assigned')
        self_filtered.write({
            'state': 'assigned',
            'stage_id': assigned_stage.id,
            'assignation_date': fields.Datetime.now(),
            'confirmed': True,
        })
        self_filtered.truck_id.x_vehicle_service_state = 'in_service'
        self_filtered._set_google_route_data()
        self_filtered.broadcastReload(reload_type='assign')

    # === PUBLIC METHODS === #
    # ToDo: Change Name?
    def action_change_service_vehicle(self, service_vehicle_id: int):
        """For Portal Users: Change the service vehicle and accept the service."""
        self.ensure_one()
        if self.truck_id.id != service_vehicle_id:
            # Previous Vehicle State
            self._change_previous_vehicle_state(self.truck_id)
            self.truck_id = service_vehicle_id
            self._set_new_service_vehicle_distance()
        self.action_confirm_vehicle()
        self.broadcastReload(reload_type='vehicle_changed')

    def _change_previous_vehicle_state(self, vehicle_id):
        # Release Previous Vehicle
        other_in_service_supplier_lines = self.search_count([
            ('id', '!=', self.id),
            ('truck_id', '=', vehicle_id.id),
            ('stage_ref', '=', 'assigned'),
        ])
        if not other_in_service_supplier_lines:
            vehicle_id.x_vehicle_service_state = 'available'

    def _set_new_service_vehicle_distance(self):
        self.ensure_one()

        if self.negotiation_type in ['base_destination', 'vehicle_destination']:
            vehicles_osrm_data = self.event_id._get_external_vehicles_location(
                float(self.event_id.location_latitude),
                float(self.event_id.location_longitude),
                vehicle_refs=[self.truck_id.x_vehicle_ref],
            )

            if len(vehicles_osrm_data):
                data = vehicles_osrm_data[0]
                self.negotiation_type = 'vehicle_destination'
                self.latitude = data.get('lat', None)
                self.longitude = data.get('lng', None)
                self.estimated_distance = data.get('distance_m', 0) / 1000
                self.estimated_duration = data.get('duration_s', 0) / 60
                self.cost_distance = data.get('duration_s', 0) / 60
                self.osrm = True
                return

        # Set Distance
        supplier_center_id = self.truck_id.x_center_id
        center_distance_id = self.event_id._get_center_distances(supplier_center_id)

        if self.negotiation_type == 'vehicle_destination':
            self.negotiation_type = 'base_destination'

        if self.negotiation_type in ['base_base', 'base_destination']:
            self.latitude = supplier_center_id.partner_latitude
            self.longitude = supplier_center_id.partner_longitude
            self.estimated_distance = center_distance_id.center_origin_distance_km
            self.estimated_duration = center_distance_id.center_origin_duration_m
            self.cost_distance = center_distance_id.center_origin_distance_km
            self.route = center_distance_id.center_origin_route
        else:
            self.estimated_distance = self.estimated_duration = self.cost_distance = 0.0
            self.bypass = True

    def _get_google_route(self, latitude1, longitude1, latitude2, longitude2):
        distance_km: float = 0.0
        duration_m: float = 0.0
        route = None
        google_distance_m, google_duration_s, google_route = (
            self.event_id.get_google_route(
                latitude1, longitude1,
                latitude2, longitude2,
            )
        )
        if google_route:
            distance_km = google_distance_m / 1000
            duration_m = google_duration_s / 60
            route = google_route
        else:
            # Wrong lat/lng?
            osrm_distance = self.event_id.get_osrm_distance(
                latitude1, longitude1,
                latitude2, longitude2,
            )
            distance_km = osrm_distance['estimated_distance']
            duration_m = osrm_distance['estimated_duration']

        return distance_km, duration_m, route

    def _set_google_route_data(self):
        for rec in self:
            if rec.negotiation_type != 'origin_destination':
                # Protect maximum distance 100 km
                if (
                    self.distance_haversine(
                        rec.latitude,
                        rec.longitude,
                        rec.event_id.location_latitude,
                        rec.event_id.location_longitude,
                    )
                    > 100.0
                ):
                    continue

                distance_km: float = 0.0
                duration_m: float = 0.0
                route = None
                if rec.negotiation_type == 'base_destination':
                    center_distance_id = self.env['ike.event.center.distance'].search([
                        ('event_id', '=', rec.event_id.id),
                        ('supplier_center_id', '=', rec.supplier_center_id.id),
                    ])

                    if not center_distance_id.center_origin_route:
                        distance_km, duration_m, route = rec._get_google_route(
                            rec.latitude,
                            rec.longitude,
                            rec.event_id.location_latitude,
                            rec.event_id.location_longitude,
                        )
                        if not center_distance_id:
                            center_distance_id = self.env['ike.event.center.distance'].create({
                                'event_id': rec.event_id.id,
                                'supplier_center_id': rec.supplier_center_id.id,
                                'center_origin_distance_km': distance_km,
                                'center_origin_duration_m': duration_m,
                                'center_origin_route': route,
                            })
                        else:
                            center_distance_id.origin_center_distance_km = distance_km
                            center_distance_id.origin_center_duration_m = duration_m
                            center_distance_id.center_origin_route = route
                    distance_km = center_distance_id.center_origin_distance_km
                    distance_km = center_distance_id.center_origin_duration_m
                    route = center_distance_id.center_origin_route
                else:
                    distance_km, duration_m, route = rec._get_google_route(
                        rec.latitude,
                        rec.longitude,
                        rec.event_id.location_latitude,
                        rec.event_id.location_longitude,
                    )
                # Set values
                rec.real_distance = distance_km
                rec.real_duration = duration_m
                rec.route = route
                if not rec.estimated_distance:
                    rec.estimated_distance = distance_km
                    rec.estimated_duration = duration_m

    # === PRIVATE METHODS === #
    def _notify_expiration(self):
        for rec in self:
            line_ids = self.search([
                ('event_id', '=', rec.event_id.id),
                ('state', '=', 'notified'),
            ], order='sequence desc')
            if line_ids:
                line_ids.action_expire()

    def _notify_acceptation(self):
        pass

    def _notify_next(self):
        for rec in self:
            if rec.assignation_type == 'electronic':
                current = rec._get_current_notified_siblings()
                if not current:
                    line_id = rec._notify_next_siblings(rec.assignation_type, limit=1)
                    if not line_id:
                        rec.event_id._search_suppliers('publication', '3')
                        rec.event_id.broadcastEventReload(3)
            elif rec.assignation_type == 'publication':
                current = rec._get_current_notified_siblings()
                if not current:
                    line_ids = rec._notify_next_siblings(rec.assignation_type, rec.priority)
                    if not line_ids:
                        next_priority = int(rec.priority) - 1
                        if next_priority >= 1:
                            rec.event_id._search_suppliers('publication', str(next_priority))
                        else:
                            rec.event_id._search_suppliers('manual')
                        rec.event_id.broadcastEventReload(3)
                elif rec.state == 'timeout':
                    available_siblings = rec._count_available_siblings()
                    timeout_id = rec.id
                    first_timeout_sibling = rec._get_first_timeout_sibling(rec.notification_date)
                    if first_timeout_sibling:
                        timeout_id = first_timeout_sibling[0]['id']
                    if not available_siblings and timeout_id == rec.id:
                        next_priority = int(rec.priority) - 1
                        if next_priority >= 1:
                            rec.event_id._search_suppliers('publication', str(next_priority))
                        else:
                            rec.event_id._search_suppliers('manual')
                        rec.event_id.broadcastEventReload(3)

    def _count_available_siblings(self):
        self.ensure_one()
        return self.search_count([
            ('event_id', '=', self.event_id.id),
            ('supplier_number', '=', self.supplier_number),
            ('search_number', '=', self.search_number),
            ('state', 'in', ['available']),
            ('assignation_type', '=', self.assignation_type),
            ('priority', '=', self.priority),
            ('display_type', '=', False),
        ])

    def _get_first_timeout_sibling(self, notification_date):
        return self.search_read([
            ('event_id', '=', self.event_id.id),
            ('supplier_number', '=', self.supplier_number),
            ('search_number', '=', self.search_number),
            ('notification_date', '=', notification_date),
            ('state', 'in', ['timeout', 'notified']),
            ('assignation_type', '=', self.assignation_type),
            ('display_type', '=', False),
        ], ['id'], limit=1)

    def _get_current_notified_siblings(self):
        self.ensure_one()
        return self.search_read([
            ('id', '!=', self.id),
            ('event_id', '=', self.event_id.id),
            ('supplier_number', '=', self.supplier_number),
            ('search_number', '=', self.search_number),
            ('state', '=', 'notified'),
            ('assignation_type', '=', self.assignation_type),
            ('display_type', '=', False),
        ], fields=['id'])

    def _notify_next_siblings(self, assignation_type, priority=None, limit=None):
        self.ensure_one()
        domain = [
            ('id', '!=', self.id),
            ('event_id', '=', self.event_id.id),
            ('supplier_number', '=', self.supplier_number),
            ('search_number', '=', self.search_number),
            ('state', 'in', ['available', 'notified']),
            ('assignation_type', '=', assignation_type),
        ]
        if priority:
            domain.append(('priority', '=', priority))

        kwargs = {}
        if limit:
            kwargs['limit'] = limit

        line_ids = self.search(domain, order='sequence', **kwargs)
        if line_ids:
            line_ids.filtered(lambda d: d.state == 'available').action_notify()

        return line_ids

    def _lock_records_by_state(self, current_state: str) -> list[int]:
        """ To avoid sending the same records multiple times from different transactions to update the record state field.

        :param state: target state.
        """
        if not self.ids:
            return []
        self._cr.execute(
            f'SELECT id FROM {self._table} WHERE id IN %s AND state = %s FOR UPDATE SKIP LOCKED', [tuple(self.ids), current_state]
        )
        return [row[0] for row in self.env.cr.fetchall()]

    # === BROADCASTS === #
    def broadcastReload(self, event_reload: bool = False, reload_type: str = ''):
        """ Broadcast notifications for internal users."""
        action_from = self.env.context.get('ike_event_action_from', 'internal')
        for rec in self:
            channel_name = f'ike_channel_event_{str(rec.event_id.id)}'
            data = {
                'id': rec.id,
                'state': rec.state,
                'stage_ref': rec.stage_ref,
                'folio': rec.folio,
                'event_id': [rec.event_id.id, rec.event_id.name],
                'supplier_id': [rec.supplier_id.id, rec.supplier_id.name],
                'action_from': action_from,
                'reload_type': reload_type,
                'event_reload': event_reload,
            }
            event_batcher.add_event_notification(
                self.env.cr.dbname,
                channel_name,
                'ike_event_supplier_reload', data, batch_timeout=2)
        self.broadcastReloadForSupplier(action_from, reload_type)

    def broadcastCancel(self, event_reload=False):
        """ Broadcast cancel notifications for internal users."""
        action_from = self.env.context.get('ike_event_action_from', 'internal')
        for rec in self:
            channel_name = f'ike_channel_event_{str(rec.event_id.id)}'
            event_batcher.add_event_notification(
                self.env.cr.dbname,
                channel_name,
                'ike_event_supplier_reload', {
                    'id': rec.id,
                    'state': rec.state,
                    'stage_ref': rec.stage_ref,
                    'folio': rec.folio,
                    'event_id': [rec.event_id.id, rec.event_id.name],
                    'supplier_id': [rec.supplier_id.id, rec.supplier_id.name],
                    'action_from': action_from,
                    'cancel_reason': rec.cancel_reason_id.name,
                    'cancel_user': rec.cancel_user_id.name,
                    'event_reload': event_reload,
                }, batch_timeout=2)
        self.broadcastCancelForSupplier(action_from)

    def broadcastReloadForSupplier(self, action_from: str = 'internal', reload_type: str = ''):
        """ Broadcast notification for portal users. """
        for rec in self:
            channel_name = f'ike_channel_supplier_{str(rec.supplier_id.id)}'
            event_batcher.add_event_notification(
                self.env.cr.dbname,
                channel_name,
                'ike_supplier_lines_reload_2', {
                    'action_from': action_from,
                    'reload_type': reload_type,
                    'id': rec.id,
                    'state': rec.state,
                    'stage_ref': rec.stage_ref,
                    'event_id': [rec.event_id.id, rec.event_id.name],
                    'supplier_id': [rec.supplier_id.id, rec.supplier_id.name],
                }, batch_timeout=2)

    def broadcastCancelForSupplier(self, action_from='internal'):
        """ Broadcast cancel notification for portal users. """
        for rec in self:
            channel_name = f'ike_channel_supplier_{str(rec.supplier_id.id)}'
            # Broadcast batches testing
            event_batcher.add_event_notification(
                self.env.cr.dbname,
                channel_name,
                'ike_supplier_lines_reload_2', {
                    'action_from': action_from,
                    'id': rec.id,
                    'state': rec.state,
                    'stage_ref': rec.stage_ref,
                    'event_id': [rec.event_id.id, rec.event_id.name],
                    'supplier_id': [rec.supplier_id.id, rec.supplier_id.name],
                    'cancel_reason': rec.cancel_reason_id.name,
                    'cancel_user': rec.cancel_user_id.name,
                }, batch_timeout=2)

    def broadcastNextSearch(self, function_name, next_uuid):
        """ Broadcast form view reload by uuid. """
        for rec in self:
            channel_name = f'ike_channel_event_{str(rec.event_id.id)}'
            # event_batcher.add_event_notification(
            #     self.env.cr.dbname,
            #     channel_name,
            #     'ike_event_next_search', {
            #         'id': rec.event_id.id,
            #         'params': {
            #             'function_name': function_name,
            #             'next_uuid': next_uuid,
            #         },
            #     }, batch_timeout=4)
            self.env['bus.bus']._sendone(
                target=channel_name,
                notification_type='ike_event_next_search',
                message={
                    'id': rec.event_id.id,
                    'params': {
                        'function_name': function_name,
                        'next_uuid': next_uuid,
                    },
                },
            )

    @staticmethod
    def distance_haversine(lat1, lng1, lat2, lng2):
        lat1 = float(lat1)
        lng1 = float(lng1)
        lat2 = float(lat2)
        lng2 = float(lng2)

        R = 6371

        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])

        distance_lat = lat2 - lat1
        distance_lng = lng2 - lng1

        a = sin(distance_lat / 2)**2 + cos(lat1) * cos(lat2) * sin(distance_lng / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c
