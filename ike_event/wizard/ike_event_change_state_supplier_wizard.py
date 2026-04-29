from datetime import timedelta
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class IkeEventChangeStateSupplierWizard(models.TransientModel):
    _name = 'ike.event.change.state.supplier.wizard'
    _description = 'Event Change State Wizard'

    # === FIELDS SUPPLIER === #
    supplier_id = fields.Many2one(
        'ike.event.supplier',
        string='Supplier',
        required=True,
        readonly=True,
        ondelete='cascade'
    )
    event_id = fields.Many2one(related='supplier_id.event_id')
    stage_id = fields.Many2one(related='supplier_id.stage_id', string='Current state')

    first_state_date = fields.Datetime(related='supplier_id.first_state_date')
    first_state_user_id = fields.Many2one(related='supplier_id.first_state_user_id')
    first_comment = fields.Text(related='supplier_id.first_comment')

    supplier_assignation_user_id = fields.Many2one(
        related='supplier_id.assignation_user_id',
        string='Assigned')
    supplier_on_route_to_start_user_id = fields.Many2one(
        related='supplier_id.on_route_to_start_user_id',
        string='On route')
    supplier_on_route_to_end_user_id = fields.Many2one(
        related='supplier_id.on_route_to_end_user_id',
        string='Arrived')
    supplier_contacted_user_id = fields.Many2one(
        related='supplier_id.contacted_user_id',
        string='Contacted')
    supplier_on_route_to_destination_start_user_id = fields.Many2one(
        related='supplier_id.on_route_to_destination_start_user_id',
        string='Route to destination')
    supplier_on_route_to_destination_end_user_id = fields.Many2one(
        related='supplier_id.on_route_to_destination_end_user_id',
        string='He arrived at his destination')
    supplier_finalized_user_id = fields.Many2one(
        related='supplier_id.finalized_user_id',
        string='Finalized')

    stage_selected_id = fields.Many2one(
        'ike.service.stage',
        string="New state",
        domain=[('ref', 'in', ['arrived', 'contacted', 'finalized'])])

    # === FIELDS STAGE === #
    # === ASSIGNED ===
    first_assignation_date = fields.Datetime(related='supplier_id.first_assignation_date')
    first_assignation_user_id = fields.Many2one(related='supplier_id.first_assignation_user_id')
    first_assignation_comment = fields.Text(related='supplier_id.first_assignation_comment')

    assignation_date = fields.Datetime(string='Assigned (datetime)')
    assignation_user_id = fields.Many2one(
        'res.users',
        string='Assigned (user)',
        default=lambda self: self.env.user
    )
    assignation_comment = fields.Text(string='Assigned (comment)')

    # === ON ROUTE ===
    first_on_route_to_user_start_date = fields.Datetime(related='supplier_id.first_on_route_to_user_start_date')
    first_on_route_to_start_user_id = fields.Many2one(related='supplier_id.first_on_route_to_start_user_id')
    first_on_route_to_start_comment = fields.Text(related='supplier_id.first_on_route_to_start_comment')

    on_route_to_user_start_date = fields.Datetime(string='On route (datetime)')
    on_route_to_start_user_id = fields.Many2one(
        'res.users',
        string='On route (user)',
        default=lambda self: self.env.user
    )
    on_route_to_start_comment = fields.Text(string='On route (comment)')

    # === ARRIVED ===
    first_on_route_to_user_end_date = fields.Datetime(related='supplier_id.first_on_route_to_user_end_date')
    first_on_route_to_end_user_id = fields.Many2one(related='supplier_id.first_on_route_to_end_user_id')
    first_on_route_to_end_comment = fields.Text(related='supplier_id.first_on_route_to_end_comment')

    on_route_to_user_end_date = fields.Datetime(string='Arrived (datetime)')
    on_route_to_end_user_id = fields.Many2one(
        'res.users',
        string='Arrived (user)',
        default=lambda self: self.env.user
    )
    on_route_to_end_comment = fields.Text(string='Arrived (comment)')

    # === CONTACTED ===
    first_contacted_date = fields.Datetime(related='supplier_id.first_contacted_date')
    first_contacted_user_id = fields.Many2one(related='supplier_id.first_contacted_user_id')
    first_contacted_comment = fields.Text(related='supplier_id.first_contacted_comment')

    contacted_date = fields.Datetime(string='Contacted (datetime)')
    contacted_user_id = fields.Many2one(
        'res.users',
        string='Contacted (user)',
        default=lambda self: self.env.user
    )
    contacted_comment = fields.Text(string='Contacted (comment)')

    # === ROUTE TO DESTINATION ===
    first_on_route_to_destination_start_date = fields.Datetime(related='supplier_id.first_on_route_to_destination_start_date')
    first_on_route_to_destination_start_user_id = fields.Many2one(related='supplier_id.first_on_route_to_destination_start_user_id')
    first_on_route_to_destination_start_comment = fields.Text(related='supplier_id.first_on_route_to_destination_start_comment')

    on_route_to_destination_start_date = fields.Datetime(string='Route to destination (datetime)')
    on_route_to_destination_start_user_id = fields.Many2one(
        'res.users',
        string='Route to destination (user)',
        default=lambda self: self.env.user
    )
    on_route_to_destination_start_comment = fields.Text(string='Route to destination (comment)')

    # === HE ARRIVED DESTINATION ===
    first_on_route_to_destination_end_date = fields.Datetime(related='supplier_id.first_on_route_to_destination_end_date')
    first_on_route_to_destination_end_user_id = fields.Many2one(related='supplier_id.first_on_route_to_destination_end_user_id')
    first_on_route_to_destination_end_comment = fields.Text(related='supplier_id.first_on_route_to_destination_end_comment')

    on_route_to_destination_end_date = fields.Datetime(string='He arrived at his destination (datetime)')
    on_route_to_destination_end_user_id = fields.Many2one(
        'res.users',
        string='He arrived at his destination (user)',
        default=lambda self: self.env.user
    )
    on_route_to_destination_end_comment = fields.Text(string='He arrived at his destination (comment)')

    # === FINALIZED ===
    first_finalized_date = fields.Datetime(related='supplier_id.first_finalized_date')
    first_finalized_user_id = fields.Many2one(related='supplier_id.first_finalized_user_id')
    first_finalized_comment = fields.Text(related='supplier_id.first_finalized_comment')

    finalized_date = fields.Datetime(string='Finalized (datetime)')
    finalized_user_id = fields.Many2one(
        'res.users',
        string='Finalized (user)',
        default=lambda self: self.env.user
    )
    finalized_comment = fields.Text(string='Finalized (comment)')

    # === COMPUTED FIELDS === #
    is_assigned_editable = fields.Boolean(compute='_compute_editable_fields')
    is_on_route_editable = fields.Boolean(compute='_compute_editable_fields')
    is_arrived_editable = fields.Boolean(compute='_compute_editable_fields')
    is_contacted_editable = fields.Boolean(compute='_compute_editable_fields')
    is_on_route_2_editable = fields.Boolean(compute='_compute_editable_fields')
    is_arrived_2_editable = fields.Boolean(compute='_compute_editable_fields')
    is_finalized_editable = fields.Boolean(compute='_compute_editable_fields')

    is_assigned_hidden = fields.Boolean(compute='_compute_state_hidden')
    is_on_route_hidden = fields.Boolean(compute='_compute_state_hidden')
    is_arrived_hidden = fields.Boolean(compute='_compute_state_hidden')
    is_contacted_hidden = fields.Boolean(compute='_compute_state_hidden')
    is_on_route_2_hidden = fields.Boolean(compute='_compute_state_hidden')
    is_arrived_2_hidden = fields.Boolean(compute='_compute_state_hidden')
    is_finalized_hidden = fields.Boolean(compute='_compute_state_hidden')

    # === DEFAULT === #
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        supplier_id = self.env.context.get('default_supplier_id') or self.env.context.get('active_id')
        if supplier_id:
            res['supplier_id'] = supplier_id
        return res

    # === METHODS COMPUTE === #
    @api.depends(
        'stage_selected_id',
        'assignation_date',
        'on_route_to_user_start_date',
        'on_route_to_user_end_date',
        'contacted_date',
        'on_route_to_destination_start_date',
        'on_route_to_destination_end_date',
        'finalized_date',
    )
    def _compute_editable_fields(self):
        for rec in self:
            selected = rec.stage_selected_id.ref if rec.stage_selected_id else None

            rec.is_assigned_editable = selected == 'assigned'
            rec.is_on_route_editable = selected == 'on_route'
            rec.is_arrived_editable = selected == 'arrived'
            rec.is_contacted_editable = selected == 'contacted'
            rec.is_on_route_2_editable = selected == 'on_route_2'
            rec.is_arrived_2_editable = selected == 'arrived_2'
            rec.is_finalized_editable = selected == 'finalized'

    @api.depends(
        'assignation_date',
        'on_route_to_user_start_date',
        'on_route_to_user_end_date',
        'contacted_date',
        'on_route_to_destination_start_date',
        'on_route_to_destination_end_date',
        'finalized_date'
    )
    def _compute_state_hidden(self):
        for rec in self:
            supplier = rec.supplier_id

            rec.is_assigned_hidden = (rec.assignation_date != supplier.assignation_date)
            rec.is_on_route_hidden = (rec.on_route_to_user_start_date != supplier.on_route_to_user_start_date)
            rec.is_arrived_hidden = (rec.on_route_to_user_end_date != supplier.on_route_to_user_end_date)
            rec.is_contacted_hidden = (rec.contacted_date != supplier.contacted_date)
            rec.is_on_route_2_hidden = (rec.on_route_to_destination_start_date != supplier.on_route_to_destination_start_date)
            rec.is_arrived_2_hidden = (rec.on_route_to_destination_end_date != supplier.on_route_to_destination_end_date)
            rec.is_finalized_hidden = (rec.finalized_date != supplier.finalized_date)

    # === METHODS ONCHANGE === #
    @api.onchange('stage_selected_id')
    def _onchange_stage(self):
        self._reload_fields_from_stage_supplier()

    # assigned
    @api.onchange('assignation_date')
    def _onchange_assignation_date(self):
        return self._validate_and_set_date('assignation_date', 'assignation_user_id', 'assignation_comment')

    # on route
    @api.onchange('on_route_to_user_start_date')
    def _onchange_on_route_to_user_start_date(self):
        return self._validate_and_set_date('on_route_to_user_start_date', 'on_route_to_start_user_id', 'on_route_to_start_comment')

    # arrived
    @api.onchange('on_route_to_user_end_date')
    def _onchange_on_route_to_user_end_date(self):
        return self._validate_and_set_date('on_route_to_user_end_date', 'on_route_to_end_user_id', 'on_route_to_end_comment')

    # contacted
    @api.onchange('contacted_date')
    def _onchange_contacted_date(self):
        return self._validate_and_set_date('contacted_date', 'contacted_user_id', 'contacted_comment')

    # route to destination
    @api.onchange('on_route_to_destination_start_date')
    def _onchange_on_route_to_destination_start_date(self):
        return self._validate_and_set_date('on_route_to_destination_start_date', 'on_route_to_destination_start_user_id', 'on_route_to_destination_start_comment')

    # he arrived destination
    @api.onchange('on_route_to_destination_end_date')
    def _onchange_on_route_to_destination_end_date(self):
        return self._validate_and_set_date('on_route_to_destination_end_date', 'on_route_to_destination_end_user_id', 'on_route_to_destination_end_comment')

    # finalized
    @api.onchange('finalized_date')
    def _onchange_finalized_date(self):
        return self._validate_and_set_date('finalized_date', 'finalized_user_id', 'finalized_comment')

    # === ACTION === #
    def action_confirm(self):
        self.ensure_one()
        if not self.stage_selected_id:
            raise ValidationError(_('Please select a stage.'))

        supplier = self.supplier_id
        stage_ref = self.stage_selected_id.ref
        vals = {}

        if stage_ref == 'assigned':
            self._action_assign(
                supplier,
                vals,
                self.assignation_date,
                self.assignation_user_id.id,
                self.assignation_comment
            )

        if stage_ref == 'on_route':
            self._action_on_route(
                supplier,
                vals,
                self.on_route_to_user_start_date,
                self.on_route_to_start_user_id.id,
                self.on_route_to_start_comment
            )

        if stage_ref == 'arrived':
            if self.on_route_to_user_end_date <= self.event_id.event_date:
                event_date = fields.Datetime.context_timestamp(self, self.event_id.event_date).strftime('%d-%m-%Y %H:%M:%S')
                raise ValidationError(_('Arrived date cannot be earlier than or equal to event date (%s)', event_date))
            else:
                self._action_on_route(
                    supplier,
                    vals,
                    self.on_route_to_user_end_date - timedelta(minutes=1),
                    self.on_route_to_start_user_id.id,
                    f'{supplier.display_name} - {self.on_route_to_user_end_date - timedelta(minutes=1)}'
                )

                self._action_arrived(
                    supplier,
                    vals,
                    self.on_route_to_user_end_date,
                    self.on_route_to_end_user_id.id,
                    self.on_route_to_end_comment
                )

        if stage_ref == 'contacted':
            if self.contacted_date <= self.event_id.event_date:
                event_date = fields.Datetime.context_timestamp(self, self.event_id.event_date).strftime('%d-%m-%Y %H:%M:%S')
                raise ValidationError(_('Contacted date cannot be earlier than or equal to event date (%s)', event_date))
            else:
                self._action_contacted(
                    supplier,
                    vals,
                    self.contacted_date,
                    self.contacted_user_id.id,
                    self.contacted_comment
                )

        if stage_ref == 'on_route_2':
            self._action_on_route_2(
                supplier,
                vals,
                self.on_route_to_destination_start_date,
                self.on_route_to_destination_start_user_id.id,
                self.on_route_to_destination_start_comment
            )

        if stage_ref == 'arrived_2':
            self._action_arrived_2(
                supplier,
                vals,
                self.on_route_to_destination_end_date,
                self.on_route_to_destination_end_user_id.id,
                self.on_route_to_destination_end_comment
            )

        if stage_ref == 'finalized':
            if self.finalized_date <= self.event_id.event_date:
                event_date = fields.Datetime.context_timestamp(self, self.event_id.event_date).strftime('%d-%m-%Y %H:%M:%S')
                raise ValidationError(_('Finalized date cannot be earlier than or equal to event date (%s)', event_date))
            else:
                self._action_on_route_2(
                    supplier,
                    vals,
                    self.finalized_date - timedelta(minutes=2),
                    self.finalized_user_id.id,
                    f'{supplier.display_name} - {self.finalized_date - timedelta(minutes=2)}'
                )

                self._action_arrived_2(
                    supplier,
                    vals,
                    self.finalized_date - timedelta(minutes=1),
                    self.finalized_user_id.id,
                    f'{supplier.display_name} - {self.finalized_date - timedelta(minutes=1)}'
                )

                self._action_finalized(
                    supplier,
                    vals,
                    self.finalized_date,
                    self.finalized_user_id.id,
                    self.finalized_comment
                )

        # if not vals:
        #     raise ValidationError(_('Invalid stage.'))

        if not supplier.first_state_date:
            vals.update({
                'first_state_date': fields.Datetime.now(),
                'first_state_user_id': self.env.user.id,
                'first_comment': _(
                    f'User: {self.env.user.display_name}'
                    f' - Datetime: {fields.Datetime.now()}'
                ),
            })

        supplier.write(vals)

        return supplier.open_change_state_supplier_wizard()

    def _validate_and_set_date(self, field_name, user_field, comment_field):
        date_value = self[field_name]

        if date_value and not self[user_field]:
            self[user_field] = self.env.user

        if date_value != self._origin[field_name]:
            self[comment_field] = False

        last_date = self._get_last_captured_date(field_name)

        date_value = fields.Datetime.to_datetime(date_value)
        last_date = fields.Datetime.to_datetime(last_date)

        if not date_value or not last_date:
            return

        if date_value <= last_date:
            self[field_name] = False

            user_tz = self.env.user.tz or 'UTC'
            tz = pytz.timezone(user_tz)

            def fmt(dt):
                if not dt:
                    return ('')
                dt_aware = fields.Datetime.to_datetime(dt)
                if not dt_aware:
                    return ('')
                return pytz.utc.localize(dt_aware).astimezone(tz).strftime('%d/%m/%Y %H:%M')

            last_date_display = pytz.utc.localize(last_date).astimezone(tz).strftime('%d/%m/%Y %H:%M')

            return {
                'warning': {
                    'title': _('Invalid date'),
                    'message': _(
                        'Date cannot be earlier than or equal to last captured date (%s).\n'
                        'Assignation: %s\n'
                        'On route: %s\n'
                        'Arrived: %s\n'
                        'Contacted: %s\n'
                        'On route to destination: %s\n'
                        'He arrived destination: %s\n'
                        'Finalized: %s',
                        last_date_display,
                        fmt(self.supplier_id.assignation_date),
                        fmt(self.supplier_id.on_route_to_user_start_date),
                        fmt(self.supplier_id.on_route_to_user_end_date),
                        fmt(self.supplier_id.contacted_date),
                        fmt(self.supplier_id.on_route_to_destination_start_date),
                        fmt(self.supplier_id.on_route_to_destination_end_date),
                        fmt(self.supplier_id.finalized_date),
                    ),
                }
            }

    def _get_last_captured_date(self, current_field: str):
        dates_supplier = {
            'assignation_date': {'sequence': 1, 'date': self.assignation_date},
            'on_route_to_user_start_date': {'sequence': 2, 'date': self.on_route_to_user_start_date},
            'on_route_to_user_end_date': {'sequence': 3, 'date': self.on_route_to_user_end_date},
            'contacted_date': {'sequence': 4, 'date': self.contacted_date},
            'on_route_to_destination_start_date': {'sequence': 5, 'date': self.on_route_to_destination_start_date},
            'on_route_to_destination_end_date': {'sequence': 6, 'date': self.on_route_to_destination_end_date},
            'finalized_date': {'sequence': 7, 'date': self.finalized_date},
        }

        current_sequence = dates_supplier[current_field]['sequence']

        filtered = [
            (v['sequence'], v['date'])
            for k, v in dates_supplier.items()
            if v['sequence'] < current_sequence and v['date']
        ]
        previous_dates = sorted(filtered, key=lambda x: x[0], reverse=True)

        return previous_dates[0][1] if previous_dates else False

    def _reload_fields_from_stage_supplier(self):
        supplier = self.supplier_id
        if not supplier:
            return
        self.assignation_date = supplier.assignation_date
        self.assignation_user_id = supplier.assignation_user_id
        self.assignation_comment = supplier.assignation_comment

        self.on_route_to_user_start_date = supplier.on_route_to_user_start_date
        self.on_route_to_start_user_id = supplier.on_route_to_start_user_id
        self.on_route_to_start_comment = supplier.on_route_to_start_comment

        self.on_route_to_user_end_date = supplier.on_route_to_user_end_date
        self.on_route_to_end_user_id = supplier.on_route_to_end_user_id
        self.on_route_to_end_comment = supplier.on_route_to_end_comment

        self.contacted_date = supplier.contacted_date
        self.contacted_user_id = supplier.contacted_user_id
        self.contacted_comment = supplier.contacted_comment

        self.on_route_to_destination_start_date = supplier.on_route_to_destination_start_date
        self.on_route_to_destination_start_user_id = supplier.on_route_to_destination_start_user_id
        self.on_route_to_destination_start_comment = supplier.on_route_to_destination_start_comment

        self.on_route_to_destination_end_date = supplier.on_route_to_destination_end_date
        self.on_route_to_destination_end_user_id = supplier.on_route_to_destination_end_user_id
        self.on_route_to_destination_end_comment = supplier.on_route_to_destination_end_comment

        self.finalized_date = supplier.finalized_date
        self.finalized_user_id = supplier.finalized_user_id
        self.finalized_comment = supplier.finalized_comment

    def _action_assign(self, supplier, vals, datetime, user, comment):
        already_assigned = bool(supplier.assignation_user_id or supplier.assignation_date)

        if already_assigned:
            supplier.write({
                'assignation_date': datetime,
                'assignation_user_id': user,
                'assignation_comment': comment,
            })
            return

        vals.update({
            'assignation_date': datetime,
            'assignation_user_id': user,
            'assignation_comment': comment,
        })

        first_date = supplier.first_assignation_date or datetime
        if not supplier.first_assignation_date:
            vals.update({
                'first_assignation_date': datetime or fields.Datetime.now(),
                'first_assignation_user_id': user,
                'first_assignation_comment': comment,
            })
            first_date = datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_assign()

    def _action_on_route(self, supplier, vals, datetime, user, comment):
        already_on_route = bool(supplier.on_route_to_start_user_id or supplier.on_route_to_user_start_date)

        if already_on_route:
            supplier.write({
                'on_route_to_user_start_date': datetime,
                'on_route_to_start_user_id': user,
                'on_route_to_start_comment': comment,
            })
            return

        vals.update({
            'on_route_to_user_start_date': datetime,
            'on_route_to_start_user_id': user,
            'on_route_to_start_comment': comment,
        })

        first_date = supplier.first_on_route_to_user_start_date or datetime
        if not supplier.first_on_route_to_user_start_date:
            vals.update({
                'first_on_route_to_user_start_date': datetime or fields.Datetime.now(),
                'first_on_route_to_start_user_id': user,
                'first_on_route_to_start_comment': comment,
            })
            first_date = datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_on_route()

    def _action_arrived(self, supplier, vals, datetime, user, comment):
        already_arrived = bool(supplier.on_route_to_end_user_id or supplier.on_route_to_user_end_date)

        if already_arrived:
            supplier.write({
                'on_route_to_user_end_date': datetime,
                'on_route_to_end_user_id': user,
                'on_route_to_end_comment': comment,
            })
            return

        vals.update({
            'on_route_to_user_end_date': datetime,
            'on_route_to_end_user_id': user,
            'on_route_to_end_comment': comment,
        })

        first_date = supplier.first_on_route_to_user_end_date or datetime
        if not supplier.first_on_route_to_user_end_date:
            vals.update({
                'first_on_route_to_user_end_date': datetime or fields.Datetime.now(),
                'first_on_route_to_end_user_id': user,
                'first_on_route_to_end_comment': comment,
            })
            first_date = datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_arrive()

    def _action_contacted(self, supplier, vals, datetime, user, comment):
        already_contacted = bool(supplier.contacted_user_id or supplier.contacted_date)

        if already_contacted:
            supplier.write({
                'contacted_date': datetime,
                'contacted_user_id': user,
                'contacted_comment': comment,
            })
            return

        vals.update({
            'contacted_date': datetime,
            'contacted_user_id': user,
            'contacted_comment': comment,
        })

        first_date = supplier.first_contacted_date or datetime
        if not supplier.first_contacted_date:
            vals.update({
                'first_contacted_date': datetime or fields.Datetime.now(),
                'first_contacted_user_id': user,
                'first_contacted_comment': comment,
            })
            first_date = datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_contact()

    def _action_on_route_2(self, supplier, vals, datetime, user, comment):
        already_on_route = bool(supplier.on_route_to_destination_start_user_id or supplier.on_route_to_destination_start_date)

        if already_on_route:
            supplier.write({
                'on_route_to_destination_start_date': datetime,
                'on_route_to_destination_start_user_id': user,
                'on_route_to_destination_start_comment': comment,
            })
            return

        vals.update({
            'on_route_to_destination_start_date': datetime,
            'on_route_to_destination_start_user_id': user,
            'on_route_to_destination_start_comment': comment,
        })

        first_date = supplier.first_on_route_to_destination_start_date or datetime
        if not supplier.first_on_route_to_destination_start_date:
            vals.update({
                'first_on_route_to_destination_start_date': datetime or fields.Datetime.now(),
                'first_on_route_to_destination_start_user_id': user,
                'first_on_route_to_destination_start_comment': comment,
            })
            first_date = datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_on_route_to_the_destination()

    def _action_arrived_2(self, supplier, vals, datetime, user, comment):
        already_arrived = bool(supplier.on_route_to_destination_end_user_id or supplier.on_route_to_destination_end_date)

        if already_arrived:
            supplier.write({
                'on_route_to_destination_end_date': datetime,
                'on_route_to_destination_end_user_id': user,
                'on_route_to_destination_end_comment': comment,
            })
            return

        vals.update({
            'on_route_to_destination_end_date': datetime,
            'on_route_to_destination_end_user_id': user,
            'on_route_to_destination_end_comment': comment,
        })

        first_date = supplier.first_on_route_to_destination_end_date or datetime
        if not supplier.first_on_route_to_destination_end_date:
            vals.update({
                'first_on_route_to_destination_end_date': datetime or fields.Datetime.now(),
                'first_on_route_to_destination_end_user_id': user,
                'first_on_route_to_destination_end_comment': comment,
            })
            first_date = datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_arrive_to_the_destination()

    def _action_finalized(self, supplier, vals, datetime, user, comment):
        already_finalized = bool(supplier.finalized_user_id or supplier.finalized_date)

        if already_finalized:
            supplier.write({
                'finalized_date': datetime,
                'finalized_user_id': user,
                'finalized_comment': comment,
            })
            return

        vals.update({
            'finalized_date': datetime,
            'finalized_user_id': user,
            'finalized_comment': comment,
        })

        first_date = supplier.first_finalized_date or datetime
        if not supplier.first_finalized_date:
            vals.update({
                'first_finalized_date': datetime or fields.Datetime.now(),
                'first_finalized_user_id': user,
                'first_finalized_comment': comment,
            })
            first_date = datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_finalize()
