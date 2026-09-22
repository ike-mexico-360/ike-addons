# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression

from .other_models.ike_event_batcher import event_batcher


class IkeEventSupplierSelection(models.Model):
    _inherit = 'ike.event.supplier'

    # === STAGE FIELDS FIRST === #
    first_state_date = fields.Datetime(string='First state datetime', tracking=True, copy=False)
    first_state_user_id = fields.Many2one(
        'res.users',
        'First state user',
        readonly=True,
        tracking=True)
    first_comment = fields.Text(string='First comment', copy=False)

    # === STAGE FIELDS ASSIGNED === #
    first_assignation_date = fields.Datetime(string="Assigned (first datetime)", tracking=True, copy=False)
    first_assignation_user_id = fields.Many2one(
        'res.users',
        'Assigned (first user)',
        readonly=True,
        tracking=True)
    first_assignation_comment = fields.Text(string='Assigned (first comment)', copy=False)

    # assignation_date = fields.Datetime(string='Assigned (datetime)', tracking=True, copy=False)
    assignation_user_id = fields.Many2one(
        'res.users',
        'Assigned (user)',
        readonly=True,
        tracking=True)
    assignation_comment = fields.Text(string='Assigned (comment)', copy=False)

    # === STAGE FIELDS CONTACTED === #
    first_contacted_date = fields.Datetime(string='Contacted (first datetime)', tracking=True, copy=False)
    first_contacted_user_id = fields.Many2one(
        'res.users',
        'Contacted (first user)',
        readonly=True,
        tracking=True)
    first_contacted_comment = fields.Text(string='Contacted (first comment)', copy=False)

    contacted_date = fields.Datetime(string='Contacted (datetime)', tracking=True, copy=False)
    contacted_user_id = fields.Many2one(
        'res.users',
        'Contacted (user)',
        readonly=True,
        tracking=True)
    contacted_comment = fields.Text(string='Contacted (comment)', copy=False)

    # === STAGE FIELDS FINALIZED === #
    first_finalized_date = fields.Datetime(string='Finalized (first datetime)', tracking=True, copy=False)
    first_finalized_user_id = fields.Many2one(
        'res.users',
        'Finalized (first user)',
        readonly=True,
        tracking=True)
    first_finalized_comment = fields.Text(string='Finalized (first comment)', copy=False)

    finalized_date = fields.Datetime(string='Finalized (datetime)', tracking=True, copy=False)
    finalized_user_id = fields.Many2one(
        'res.users',
        'Finalized (user)',
        readonly=True,
        tracking=True)
    finalized_comment = fields.Text(string='Finalized (comment)', copy=False)

    # === STAGED LINE PROGRESS FIELDS === #
    on_route_to_user_start_date_widget = fields.Datetime()
    on_route_to_user_end_date_widget = fields.Datetime()
    on_route_to_destination_start_date_widget = fields.Datetime()
    on_route_to_destination_end_date_widget = fields.Datetime()

    # === STAGE FIELDS ON ROUTE === #
    first_on_route_to_user_start_date = fields.Datetime(string='On route (first datetime)', tracking=True, copy=False)
    first_on_route_to_start_user_id = fields.Many2one(
        'res.users',
        'On route (first user)',
        readonly=True,
        tracking=True)
    first_on_route_to_start_comment = fields.Text(string='On route (first comment)', tracking=True, copy=False)

    on_route_to_user_start_date = fields.Datetime(string='On route (datetime)', tracking=True, copy=False)
    on_route_to_start_user_id = fields.Many2one(
        'res.users', 'On route (user)',
        readonly=True,
        tracking=True)
    on_route_to_start_comment = fields.Text(string='On route (comment)', tracking=True, copy=False)

    # === STAGE FIELDS ARRIVED === #
    first_on_route_to_user_end_date = fields.Datetime(string='Arrived (first datetime)', tracking=True, copy=False)
    first_on_route_to_end_user_id = fields.Many2one(
        'res.users',
        'Arrived (first user)',
        readonly=True,
        tracking=True)
    first_on_route_to_end_comment = fields.Text(string='Arrived (first comment)', tracking=True, copy=False)

    on_route_to_user_end_date = fields.Datetime(string='Arrived (datetime)', tracking=True, copy=False)
    on_route_to_end_user_id = fields.Many2one(
        'res.users', 'Arrived (user)',
        readonly=True,
        tracking=True)
    on_route_to_end_comment = fields.Text(string='Arrived (comment)', tracking=True, copy=False)

    # === STAGE FIELDS ROUTE TO DESTINATION === #
    first_on_route_to_destination_start_date = fields.Datetime(
        string='Route to destination (first datetime)',
        tracking=True,
        copy=False)
    first_on_route_to_destination_start_user_id = fields.Many2one(
        'res.users',
        'Route to destination (first user)',
        readonly=True,
        tracking=True)
    first_on_route_to_destination_start_comment = fields.Text(
        string='Route to destination (first comment)',
        tracking=True,
        copy=False)

    on_route_to_destination_start_date = fields.Datetime(
        string='Route to destination (datetime)',
        tracking=True,
        copy=False)
    on_route_to_destination_start_user_id = fields.Many2one(
        'res.users', 'Route to destination (user)',
        readonly=True,
        tracking=True)
    on_route_to_destination_start_comment = fields.Text(
        string='Route to destination (comment)',
        tracking=True,
        copy=False)

    # === STAGE FIELD ARRIVED DESTINATION === #
    first_on_route_to_destination_end_date = fields.Datetime(
        string='He arrived at his destination (first datetime)',
        tracking=True,
        copy=False)
    first_on_route_to_destination_end_user_id = fields.Many2one(
        'res.users',
        'He arrived at his destination (first user)',
        readonly=True,
        tracking=True)
    first_on_route_to_destination_end_comment = fields.Text(
        string='He arrived at his destination (first comment)',
        tracking=True,
        copy=False)

    on_route_to_destination_end_date = fields.Datetime(
        string='He arrived at his destination (datetime)',
        tracking=True,
        copy=False)
    on_route_to_destination_end_user_id = fields.Many2one(
        'res.users',
        'He arrived at his destination (user)',
        readonly=True,
        tracking=True)
    on_route_to_destination_end_comment = fields.Text(
        string='He arrived at his destination (comment)',
        tracking=True,
        copy=False)

    travel_progress_percent = fields.Float(string="Travel Progress (%)")

    # === STAGE FIELDS CANCEL === #
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
    cancelled = fields.Boolean(default=False, copy=False)
    cause_rate = fields.Boolean(default=True, index=True, readonly=True, copy=False)

    # == STAGE ACTIONS == #
    def action_on_route(self):
        supplier_on_route_stage = self.env.ref('ike_event.ike_service_stage_on_route')
        event_stage_assigned = self.env.ref('ike_event.ike_event_stage_assigned')
        for rec in self:
            rec.stage_id = supplier_on_route_stage.id
            rec.on_route_to_user_start_date_widget = fields.Datetime.now()
            # Si el evento aún está en etapa asignado, se puede pasar a la etapa en ruta
            if rec.event_id.stage_ref == event_stage_assigned.ref and rec.event_id.step_number == 1:
                rec.event_id.with_context(dict(
                    current_stage_id=rec.event_id.stage_id.id,
                    current_step_number=rec.event_id.step_number,
                )).action_forward()
                rec.broadcastReload(event_reload=True, reload_type='on_route')

    def action_arrive(self):
        arrived_stage = self.env.ref('ike_event.ike_service_stage_arrived')
        for rec in self:
            rec.stage_id = arrived_stage.id
            rec.on_route_to_user_end_date_widget = fields.Datetime.now()
            rec.broadcastReload(event_reload=True, reload_type='arrive')

    def action_contact(self):
        contacted_stage = self.env.ref('ike_event.ike_service_stage_contacted')
        for rec in self:
            rec.stage_id = contacted_stage.id
            rec.broadcastReload(reload_type='contact')

    def action_on_route_to_the_destination(self):
        on_route_stage = self.env.ref('ike_event.ike_service_stage_on_route_2')
        for rec in self:
            rec.stage_id = on_route_stage.id
            rec.on_route_to_destination_start_date_widget = fields.Datetime.now()
            rec.broadcastReload(reload_type='on_route_to_the_destination')

    def action_arrive_to_the_destination(self):
        arrived_stage = self.env.ref('ike_event.ike_service_stage_arrived_2')
        for rec in self:
            rec.stage_id = arrived_stage.id
            rec.on_route_to_destination_end_date_widget = fields.Datetime.now()
            rec.broadcastReload(reload_type='arrive_to_the_destination')

    def action_finalize(self):
        self.ensure_one()
        supplier_stage_finalized = self.env.ref('ike_event.ike_service_stage_finalized').id

        self.stage_id = supplier_stage_finalized
        # Vehicle State
        self.truck_id.x_vehicle_service_state = 'available'

        # Event Completed: validation inside
        self.event_id.action_completed()
        if self.event_id.stage_id.ref == 'completed' and not self.is_generic_supplier and not self.purchase_supplier_id:
            self.event_id.action_verify()

        # Get Distance km
        negotiation_type = self.negotiation_type
        total_distance_km = self.cost_distance
        if negotiation_type == 'base_base':
            total_distance_km = (self.cost_distance + (self.event_id.destination_distance or 0)) * 2.0
        elif negotiation_type in ['base_destination', 'vehicle_destination']:
            total_distance_km += (self.event_id.destination_distance or 0)
        elif negotiation_type == 'origin_destination':
            total_distance_km = (self.event_id.destination_distance or 0)
        elif negotiation_type == 'base_concept':
            total_distance_km = 0.0
        else:
            total_distance_km = 0.0
        total_distance_km = int(-(-total_distance_km // 1))  # To integer

        # Event reload
        self.broadcastReload(event_reload=True, reload_type='finalize')

    def action_from_progress_state(self, progress_state):
        self.ensure_one()
        actions = {
            '0': self.action_assign,
            '1': self.action_on_route,
            '2': self.action_arrive,
            '3': self.action_contact,
            '4': self.action_on_route_to_the_destination,
            '5': self.action_arrive_to_the_destination,
            '6': self.action_finalize,
        }

        if progress_state == '1':
            # On Route
            on_route_to_user_start_date = fields.Datetime.now()
            on_route_to_user_id = self.env.user
            on_route_to_start_comment = f'{self.supplier_id.display_name} - {on_route_to_user_start_date}'

            if not self.first_on_route_to_user_start_date:
                self.write({
                    'first_on_route_to_user_start_date': on_route_to_user_start_date,
                    'first_on_route_to_start_user_id': on_route_to_user_id.id,
                    'first_on_route_to_start_comment': _(
                        f'On Route - Datetime: {on_route_to_user_start_date}'
                    ),
                })

            self.write({
                'on_route_to_user_start_date': on_route_to_user_start_date,
                'on_route_to_start_user_id': on_route_to_user_id.id,
                'on_route_to_start_comment': on_route_to_start_comment,
            })

        elif progress_state == '2':
            # Arrived
            arrive_date = fields.Datetime.now()
            arrive_user_id = self.env.user
            arrive_comment = f'{self.supplier_id.display_name} - {arrive_date}'

            if not self.first_on_route_to_user_end_date:
                self.write({
                    'first_on_route_to_user_end_date': arrive_date,
                    'first_on_route_to_end_user_id': arrive_user_id.id,
                    'first_on_route_to_end_comment': arrive_comment,
                })

            self.write({
                'on_route_to_user_end_date': arrive_date,
                'on_route_to_end_user_id': arrive_user_id.id,
                'on_route_to_end_comment': arrive_comment,
            })

        elif progress_state == '3':
            # Contacted
            contacted_date = fields.Datetime.now()
            contacted_user_id = self.env.user
            contacted_comment = f'{self.supplier_id.display_name} - {contacted_date}'

            if not self.first_contacted_date:
                self.write({
                    'first_contacted_date': contacted_date,
                    'first_contacted_user_id': contacted_user_id.id,
                    'first_contacted_comment': contacted_comment,
                })

            self.write({
                'contacted_date': contacted_date,
                'contacted_user_id': contacted_user_id.id,
                'contacted_comment': contacted_comment,
            })

        elif progress_state == '4':
            # On Route to Destiny
            on_route_to_destination_start_date = fields.Datetime.now()
            on_route_to_destination_start_user_id = self.env.user
            on_route_to_destination_start_comment = f'{self.supplier_id.display_name} - {on_route_to_destination_start_date}'

            if not self.first_on_route_to_destination_start_date:
                self.write({
                    'first_on_route_to_destination_start_date': on_route_to_destination_start_date,
                    'first_on_route_to_destination_start_user_id': on_route_to_destination_start_user_id.id,
                    'first_on_route_to_destination_start_comment': on_route_to_destination_start_comment,
                })

            self.write({
                'on_route_to_destination_start_date': on_route_to_destination_start_date,
                'on_route_to_destination_start_user_id': on_route_to_destination_start_user_id.id,
                'on_route_to_destination_start_comment': on_route_to_destination_start_comment,
            })

        elif progress_state == '5':
            # Arrived to destination
            on_route_to_destination_end_date = fields.Datetime.now()
            on_route_to_destination_end_user_id = self.env.user
            on_route_to_destination_end_comment = f'{self.supplier_id.display_name} - {on_route_to_destination_end_date}'

            if not self.first_on_route_to_destination_end_date:
                self.write({
                    'first_on_route_to_destination_end_date': on_route_to_destination_end_date,
                    'first_on_route_to_destination_end_user_id': on_route_to_destination_end_user_id.id,
                    'first_on_route_to_destination_end_comment': on_route_to_destination_end_comment,
                })

            self.write({
                'on_route_to_destination_end_date': on_route_to_destination_end_date,
                'on_route_to_destination_end_user_id': on_route_to_destination_end_user_id.id,
                'on_route_to_destination_end_comment': on_route_to_destination_end_comment,
            })

        elif progress_state == '6':
            # Finalized
            finalized_date = fields.Datetime.now()
            finalized_user_id = self.env.user
            finalized_comment = f'{self.supplier_id.display_name} - {finalized_date}'

            if not self.first_finalized_date:
                self.write({
                    'first_finalized_date': finalized_date,
                    'first_finalized_user_id': finalized_user_id.id,
                    'first_finalized_comment': finalized_comment,
                })

            self.write({
                'finalized_date': finalized_date,
                'finalized_user_id': finalized_user_id.id,
                'finalized_comment': finalized_comment,
            })

        action = actions.get(str(progress_state))
        if action:
            action()

    def action_open_manual_finalize_wizard(self):
        # action_from = self.env.context.get('action_from', 'internal')  # internal/portal/app
        action_name = 'action_manual_finalize'
        view_id = self.env.ref('ike_event.ike_event_confirm_wizard_view_form').id
        return {
            'name': self.supplier_id.display_name + " " + _('Finalize'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'ike.event.confirm.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_res_model': 'ike.event.supplier',
                'default_res_ids': str(self.mapped('id')),
                'default_action_name': action_name,
                'ike_event_supplier_finalize': True,
                'is_confirm': True,
            }
        }

    def action_manual_finalize(self, other_reason: str):
        # ToDo: add required params and save it. Adapt ike.event.confirm.wizard
        self.action_finalize()

    def action_create_purchase_order(self):
        pass

    # === ACTIONS CHANGE STATE WIZARD === #
    def open_change_state_supplier_wizard(self):
        if self.scheduled and not self.confirmed:
            raise UserError(_("Clocks cannot be modified until the vehicle is confirmed."))

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
                'default_event_supplier_id': self.id,
            }
        }

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

        self_filtered.cancel_reason_id = cancel_reason_id
        for rec in self_filtered:
            waiting_time = 0
            coverage = next((x for x in supplier_coverages if x.get("supplier_id") == 2), None)
            if coverage:
                waiting_time = coverage.get('waiting_time', 0)
            time_passed = fields.Datetime.now() - rec.acceptance_date
            rec.cancel_on_time = time_passed.total_seconds() / 60 <= waiting_time

            if rec.cancel_on_time or state == 'cancel_supplier' or rec.cancel_reason_id.from_supplier:
                rec.cause_rate = False
                rec._set_supplier_cost_zero()
            else:
                rec._set_supplier_cost_cancelled()

            # Vehicle State
            rec.truck_id.x_vehicle_service_state = 'available'

            # Update next base supplier number
            if rec.supplier_number == rec.event_id.base_supplier_number:
                rec.event_id.base_supplier_number = rec.event_id.supplier_number + 1

        # Common
        stage_cancel_id = self.env.ref('ike_event.ike_service_stage_cancelled').id
        self_filtered.cancel_date = fields.Datetime.now()
        self_filtered.state = state
        self_filtered.stage_id = stage_cancel_id
        self_filtered.cancel_user_id = self.env.user.id
        self_filtered.cancel_from = self.env.context.get('ike_event_action_from', 'internal')
        self_filtered.cancel_reason_text = reason_text
        self_filtered.cancelled = True
        self_filtered.broadcastCancel(True)

    def _set_supplier_cost_zero(self):
        for rec in self:
            supplier_product_ids = rec.supplier_product_ids.filtered(
                lambda x: x.display_type != 'line_section')
            for product_line in supplier_product_ids:
                product_line.write({'base_unit_price': 0.0})

    def _set_supplier_cost_cancelled(self):
        for rec in self:
            # supplier_id = rec.supplier_id
            supplier_product_ids = rec.supplier_product_ids.filtered(
                lambda x: x.display_type != 'line_section')
            # matrix = rec.event_id.get_supplier_product_matrix_lines(
            #     supplier_id.id, supplier_product_ids.mapped('product_id').ids)

            # cancelled_matrix = matrix.filtered(lambda x: x.supplier_status_id.ref == 'cancelled')

            for product_line in supplier_product_ids:
                product_line.write({'base_unit_price': product_line.base_cancel_price})

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
