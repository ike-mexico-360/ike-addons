# -*- coding: utf-8 -*-

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
    assignation_date = fields.Datetime(tracking=True, copy=False)
    contacted_date = fields.Datetime(tracking=True, copy=False)
    contacted_user_id = fields.Many2one('res.users', 'Contacted user', readonly=True, tracking=True)
    finalized_date = fields.Datetime(tracking=True, copy=False)
    finalized_user_id = fields.Many2one('res.users', 'Finalized User', readonly=True, tracking=True)
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
        self_filtered.state = 'notified'
        self_filtered.notification_date = fields.Datetime.now()
        self_filtered.broadcastReload()

    def action_notify_operator(self):
        self_filtered = self.filtered(lambda x: x.state == 'accepted')
        self_filtered.state = 'assigned'
        self_filtered.assignation_date = fields.Datetime.now()
        self_filtered.broadcastReload()

    def action_accept(self):
        self_filtered = self.filtered(lambda x: x.state == 'notified')
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
                    rec.estimated_distance = (destination_distance_m or rec.estimated_distance) / 1000
                    rec.estimated_duration = (destination_duration_s or rec.estimated_duration) / 60
                    rec.route = destination_route
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
        self_filtered.state = 'rejected'
        self_filtered.rejection_date = fields.Datetime.now()
        self_filtered.broadcastReload()
        if not self.env.context.get('not_notify_next'):
            self_filtered._notify_next()

    def action_timeout(self):
        self_filtered = self.filtered(lambda x: x.state == 'notified')
        self_filtered.state = 'timeout'
        self_filtered.rejection_date = fields.Datetime.now()
        self_filtered.broadcastReload()
        if not self.env.context.get('not_notify_next'):
            self_filtered._notify_next()

    def action_expire(self):
        self_filtered = self.filtered(lambda x: x.state == 'notified')
        self_filtered.state = 'expired'
        self_filtered.rejection_date = fields.Datetime.now()
        self_filtered.broadcastReload()

    # === NOTIFICATION === #
    def broadcastReload(self, event_reload=False):
        """ Broadcast notifications for internal users."""
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
                    'event_reload': event_reload,
                }, batch_timeout=2)
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
            elif rec.assignation_type == 'publication':
                current = rec._get_current_notified_siblings()
                if not current:
                    line_ids = rec._notify_next_siblings(rec.assignation_type, rec.priority)
                    if not line_ids:
                        next_priority = int(rec.priority) - 1
                        if next_priority >= 0:
                            # rec._notify_next_siblings(rec.assignation_type, str(next_priority))
                            next_uuid = uuid4()
                            rec.event_id.next_search_uuid = next_uuid
                            function_name = 'search_publication_suppliers_' + str(next_priority)
                            rec.broadcastNextSearch(function_name, next_uuid)

    def _get_current_notified_siblings(self):
        self.ensure_one()
        return self.search_read([
            ('id', '!=', self.id),
            ('event_id', '=', self.event_id.id),
            ('supplier_number', '=', self.supplier_number),
            ('state', '=', 'notified'),
            ('assignation_type', '=', self.assignation_type),
            ('priority', '=', self.priority),
        ], fields=['id'])

    def _notify_next_siblings(self, assignation_type, priority=None, limit=None):
        self.ensure_one()
        domain = [
            ('id', '!=', self.id),
            ('event_id', '=', self.event_id.id),
            ('supplier_number', '=', self.supplier_number),
            ('state', '=', 'available'),
            ('assignation_type', '=', assignation_type),
        ]
        if priority:
            domain.append(('priority', '=', priority))

        kwargs = {}
        if limit:
            kwargs['limit'] = limit

        line_ids = self.search(domain, order='sequence', **kwargs)
        if line_ids:
            line_ids.action_notify()

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
                'default_event_id': self.event_id.id if self.event_id else False,
                'default_supplier_id': self.supplier_id.id if self.supplier_id else False,
                'default_supplier_number': self.supplier_number,
                'default_stage_id': self.stage_id.id if self.stage_id else False
            }
        }
