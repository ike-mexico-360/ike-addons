# -*- coding: utf-8 -*-

import time

from uuid import uuid4

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

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
    elapsed_time_s = fields.Integer(compute='_compute_elapsed_time_s')
    # === STAGE FIELDS FIRST === #
    first_state_date = fields.Datetime(string='First state datetime', tracking=True, copy=False)
    first_state_user_id = fields.Many2one(
        'res.users',
        'First state user',
        readonly=True,
        tracking=True)
    first_comment = fields.Text(string='First comment', tracking=True, copy=False)
    # === STAGE FIELDS ASSIGNED === #
    first_assignation_date = fields.Datetime(string="Assigned (first datetime)", tracking=True, copy=False)
    first_assignation_user_id = fields.Many2one(
        'res.users',
        'Assigned (first user)',
        readonly=True,
        tracking=True)
    first_assignation_comment = fields.Text(string='Assigned (first comment)', tracking=True, copy=False)

    assignation_date = fields.Datetime(string='Assigned (datetime)', tracking=True, copy=False)
    assignation_user_id = fields.Many2one(
        'res.users',
        'Assigned (user)',
        readonly=True,
        tracking=True)
    assignation_comment = fields.Text(string='Assigned (comment)', tracking=True, copy=False)

    # === STAGE FIELDS CONTACTED === #
    first_contacted_date = fields.Datetime(string='Contacted (first datetime)', tracking=True, copy=False)
    first_contacted_user_id = fields.Many2one(
        'res.users',
        'Contacted (first user)',
        readonly=True,
        tracking=True)
    first_contacted_comment = fields.Text(string='Contacted (first comment)', tracking=True, copy=False)

    contacted_date = fields.Datetime(string='Contacted (datetime)', tracking=True, copy=False)
    contacted_user_id = fields.Many2one(
        'res.users',
        'Contacted (user)',
        readonly=True,
        tracking=True)
    contacted_comment = fields.Text(string='Contacted (comment)', tracking=True, copy=False)

    # === STAGE FIELDS FINALIZED === #
    first_finalized_date = fields.Datetime(string='Finalized (first datetime)', tracking=True, copy=False)
    first_finalized_user_id = fields.Many2one(
        'res.users',
        'Finalized (first user)',
        readonly=True,
        tracking=True)
    first_finalized_comment = fields.Text(string='Finalized (first comment)', tracking=True, copy=False)

    finalized_date = fields.Datetime(string='Finalized (datetime)', tracking=True, copy=False)
    finalized_user_id = fields.Many2one(
        'res.users',
        'Finalized (user)',
        readonly=True,
        tracking=True)
    finalized_comment = fields.Text(string='Finalized (comment)', tracking=True, copy=False)

    cancel_date = fields.Datetime(tracking=True, copy=False)
    cancel_reason_id = fields.Many2one('ike.event.cancellation.reason', 'Cancel Reason', readonly=True, tracking=True)
    cancel_user_id = fields.Many2one('res.users', 'Cancel User', readonly=True, tracking=True)
    cancel_from = fields.Selection([
        ('internal', 'Internal'),
        ('control_panel', 'Control Panel'),
        ('app_mobile', 'App Mobile'),
    ], string='Cancel From')
    cancel_reason_text = fields.Text()
    cancel_on_time = fields.Boolean(readonly=True, copy=False)

    selected = fields.Boolean(default=False, copy=False)
    cancelled = fields.Boolean(default=False, copy=False)
    cause_rate = fields.Boolean(default=True, index=True, readonly=True, copy=False)
    timer_duration = fields.Integer(help='Maximum timer duration, in seconds.', default=600, copy=False)
    is_manual = fields.Boolean(default=True)

    # === COMPUTES === #
    def _compute_elapsed_time_s(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state == 'notified':
                rec.elapsed_time_s = max((now - rec.notification_date).total_seconds(), 0)
            else:
                rec.elapsed_time_s = 0

    # === ACTIONS === #
    def action_reset(self):
        self.state = 'available'
        self.selected = False
        self.notification_date = False
        self.acceptance_date = False
        self.rejection_date = False
        self.broadcastReload()

    def action_notify(self):
        self_filtered = self.filtered(lambda x: x.state == 'available')
        if not self_filtered:
            return
        self_filtered.state = 'notified'
        self_filtered.notification_date = fields.Datetime.now()
        self_filtered.broadcastReload()

    def action_notify_operator(self):
        self_filtered = self.filtered(lambda x: x.state == 'accepted')
        if not self_filtered:
            return
        self_filtered.state = 'assigned'
        self_filtered.assignation_date = fields.Datetime.now()
        self_filtered.broadcastReload()

    def action_accept(self):
        self_filtered = self.filtered(lambda x: x.state == 'notified')
        if not self_filtered:
            return
        self_filtered.state = 'accepted'
        self_filtered.selected = True
        self_filtered.acceptance_date = fields.Datetime.now()

        for rec in self_filtered:
            if not rec.latitude or not rec.longitude:
                raise ValidationError('No latitude or longitude was assigned to the vehicle.')
            # Folio
            rec.folio = self_filtered.env['ir.sequence'].next_by_code('ike.event.supplier')
            # Acceptance Duration
            difference = rec.acceptance_date - (rec.event_id.supplier_search_date or rec.acceptance_date)
            rec.acceptance_duration = int(difference.total_seconds())
            # Vehicle state
            rec.truck_id.x_vehicle_service_state = 'in_service'
            # Set Google Route
            if not rec.route:
                destination_distance_m, destination_duration_s, destination_route = (
                    rec.event_id.get_destination_route(
                        rec.latitude,
                        rec.longitude,
                        rec.event_id.location_latitude,
                        rec.event_id.location_longitude,
                    )
                )
                if destination_route:
                    rec.route = destination_route
                    distance_km = (destination_distance_m or rec.estimated_distance) / 1000
                    duration_m = (destination_duration_s or rec.estimated_duration) / 60
                    rec.real_distance = distance_km
                    rec.real_duration = duration_m
                    if not rec.estimated_distance:
                        rec.estimated_distance = distance_km
                        rec.estimated_duration = duration_m

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
                    rec.event_id.sudo().action_forward()
            # Broadcast
            rec.broadcastReload(event_reload=use_action_forward)

    def action_reject(self):
        self_filtered = self.filtered(lambda x: x.state == 'notified')
        if not self_filtered:
            return
        self_filtered.state = 'rejected'
        self_filtered.rejection_date = fields.Datetime.now()
        self_filtered.broadcastReload()
        if not self.env.context.get('not_notify_next'):
            self_filtered._notify_next()

    def action_timeout(self):
        self_filtered = self.filtered(lambda x: x.state == 'notified')
        if not self_filtered:
            return
        with self.env.cr.savepoint():
            self_filtered.state = 'timeout'
            self_filtered.rejection_date = fields.Datetime.now()
        self_filtered.broadcastReload()
        if not self.env.context.get('not_notify_next'):
            self_filtered._notify_next()

    def action_expire(self):
        self_filtered = self.filtered(lambda x: x.state == 'notified')
        if not self_filtered:
            return
        self_filtered.state = 'expired'
        self_filtered.rejection_date = fields.Datetime.now()
        self_filtered.broadcastReload()

    # === NOTIFICATION === #
    def broadcastReload(self, event_reload=False):
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
                'event_reload': event_reload,
            }
            event_batcher.add_event_notification(
                self.env.cr.dbname,
                channel_name,
                'ike_event_supplier_reload', data, batch_timeout=2)
        self.broadcastReloadForSupplier(action_from)

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

    def broadcastReloadForSupplier(self, action_from='internal'):
        """ Broadcast notification for portal users. """
        for rec in self:
            channel_name = f'ike_channel_supplier_{str(rec.supplier_id.id)}'
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
                        # rec._notify_next_siblings(assignation_type='publication', priority='3')
                        next_uuid = uuid4()
                        rec.event_id.next_search_uuid = next_uuid
                        rec.broadcastNextSearch('search_publication_suppliers_3', next_uuid)

                        # TESTING
                        # rec.event_id.next_search_suppliers({
                        #     'function_name': 'search_publication_suppliers_3',
                        #     'next_uuid': next_uuid,
                        # })
                        # rec.event_id.broadcastEventReload()
            elif rec.assignation_type == 'publication':
                current = rec._get_current_notified_siblings()
                if not current:
                    line_ids = rec._notify_next_siblings(rec.assignation_type, rec.priority)
                    if not line_ids:
                        next_priority = int(rec.priority) - 1
                        if next_priority >= 1:
                            # rec._notify_next_siblings(rec.assignation_type, str(next_priority))
                            next_uuid = uuid4()
                            rec.event_id.next_search_uuid = next_uuid
                            function_name = 'search_publication_suppliers_' + str(next_priority)
                            rec.broadcastNextSearch(function_name, next_uuid)

                            # TESTING: NOT WORKING, even without postcommit function. :C
                            # rec.event_id.next_search_suppliers({
                            #     'function_name': function_name,
                            #     'next_uuid': next_uuid,
                            # })
                            # rec.event_id.broadcastEventReload()
                elif rec.state == 'timeout':
                    available_siblings = rec._count_available_siblings()
                    timeout_id = rec.id
                    first_timeout_sibling = rec._get_first_timeout_sibling(rec.notification_date)
                    if first_timeout_sibling:
                        timeout_id = first_timeout_sibling[0]['id']
                    if not available_siblings and timeout_id == rec.id:
                        next_priority = int(rec.priority) - 1
                        if next_priority >= 1:
                            # rec._notify_next_siblings(rec.assignation_type, str(next_priority))
                            next_uuid = uuid4()
                            rec.event_id.next_search_uuid = next_uuid
                            function_name = 'search_publication_suppliers_' + str(next_priority)
                            rec.broadcastNextSearch(function_name, next_uuid)

                            # TESTING: NOT WORKING, even without postcommit function. :C
                            # @self.env.cr.postcommit.add
                            # def postcommit_next_search_suppliers(self):
                            #     rec.event_id.next_search_suppliers({
                            #         'function_name': function_name,
                            #         'next_uuid': next_uuid,
                            #     })
                            # rec.event_id.broadcastEventReload()

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

    # === ACTIONS CANCEL === #
    def action_cancel(self, cancel_reason_id: int, reason_text=None):
        """ Cancelled by User """
        # ToDo: event cancelled requirements?
        self._action_cancel('cancel', cancel_reason_id, reason_text)

    def action_event_cancel(self, cancel_reason_id: int, reason_text=None):
        """ Entire event Cancelled by User """
        # ToDo: event cancelled requirements?
        self._action_cancel('cancel_event', cancel_reason_id, reason_text)

    def action_supplier_cancel(self, cancel_reason_id: int, reason_text=None):
        """ Cancelled by Supplier """
        # ToDo: cancelled by supplier requirements
        self._action_cancel('cancel_supplier', cancel_reason_id, reason_text)

    def _action_cancel(self, state, cancel_reason_id: int, reason_text=None):
        # ToDo: global cancel requirements?
        self_filtered = self.filtered(lambda x: x.state in ['accepted', 'assigned'] and not x.stage_ref == 'finalized')

        suppliers = self_filtered.mapped('supplier_id.id')
        suppliers = list(set(suppliers))
        supplier_coverages = self.env['custom.supplier.coverage.configuration'].sudo().search_read([
            ('supplier_id', 'in', suppliers)
        ], ['supplier_id', 'waiting_time'], order='id desc', limit=1)
        for rec in self_filtered:
            waiting_time = 0
            coverage = next((x for x in supplier_coverages if x.get("supplier_id") == 2), None)
            if coverage:
                waiting_time = coverage.get('waiting_time', 0)
            time_passed = fields.Datetime.now() - rec.acceptance_date
            rec.cancel_on_time = time_passed.total_seconds() / 60 <= waiting_time

            if state == 'cancel_supplier' or rec.cancel_on_time:
                rec.cause_rate = False

            # Vehicle State
            rec.truck_id.x_vehicle_service_state = 'available'

            # Update next base supplier number
            if rec.supplier_number == rec.event_id.base_supplier_number:
                rec.event_id.base_supplier_number = rec.event_id.supplier_number + 1
        # Common
        self_filtered.cancel_date = fields.Datetime.now()
        self_filtered.state = state
        self_filtered.cancel_reason_id = cancel_reason_id
        self_filtered.cancel_user_id = self.env.user.id
        self_filtered.cancel_from = self.env.context.get('ike_event_action_from', 'internal')
        self_filtered.cancel_reason_text = reason_text
        self_filtered.cancelled = True
        self_filtered.broadcastCancel()

    # === ACTIONS CANCEL WIZARD === #
    def open_cancel_wizard(self):
        return self._open_cancel_wizard('action_cancel')

    def open_event_cancel_wizard(self):
        return self._open_cancel_wizard('action_event_cancel')

    def open_supplier_cancel_wizard(self):
        return self._open_cancel_wizard('action_supplier_cancel')

    def _open_cancel_wizard(self, action_name):
        view_id = self.env.ref('ike_event.ike_event_confirm_wizard_view_form').id
        self_filtered = self.filtered(lambda x: x.state in [
            'accepted', 'assigned',
        ])
        if self_filtered:
            return {
                'name': self.supplier_id.display_name + " " + _('Cancel'),
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'ike.event.confirm.wizard',
                'view_id': view_id,
                'views': [(view_id, 'form')],
                'target': 'new',
                'context': {
                    'default_res_model': 'ike.event.supplier',
                    'default_res_ids': str(self_filtered.mapped('id')),
                    'default_action_name': action_name,
                    'ike_event_supplier_cancel': True,
                    'is_cancel': True,
                }
            }

    # === ACTIONS CHANGE STATE WIZARD === #
    def open_change_state_supplier_wizard(self):
        return self._open_change_state_supplier_wizard()

    def _open_change_state_supplier_wizard(self):
        self.ensure_one()

        view_id = self.env.ref('ike_event.ike_event_change_state_supplier_wizard_form').id

        return {
            'name': self.supplier_id.display_name + " " + _('Change state'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'ike.event.change.state.supplier.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_supplier_id': self.id,
            }
        }
