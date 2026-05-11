from datetime import timedelta

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

    stage_selected = fields.Selection([
        ('arrived', 'Arrived'),
        ('contacted', 'Contacted'),
        ('finalized', 'Finalized'),
    ], string='Stage', required=True)

    # === ARRIVED ===
    first_on_route_to_user_end_date = fields.Datetime(related='supplier_id.first_on_route_to_user_end_date')
    first_on_route_to_end_user_id = fields.Many2one(related='supplier_id.first_on_route_to_end_user_id')
    first_on_route_to_end_comment = fields.Text(related='supplier_id.first_on_route_to_end_comment')

    on_route_to_user_end_date = fields.Datetime(string='Arrived (datetime)')
    on_route_to_end_user_id = fields.Many2one(
        'res.users',
        string='Arrived (user)'
    )
    on_route_to_end_comment = fields.Text(string='Arrived (comment)')

    # === CONTACTED ===
    first_contacted_date = fields.Datetime(related='supplier_id.first_contacted_date')
    first_contacted_user_id = fields.Many2one(related='supplier_id.first_contacted_user_id')
    first_contacted_comment = fields.Text(related='supplier_id.first_contacted_comment')

    contacted_date = fields.Datetime(string='Contacted (datetime)')
    contacted_user_id = fields.Many2one(
        'res.users',
        string='Contacted (user)'
    )
    contacted_comment = fields.Text(string='Contacted (comment)')

    # === FINALIZED ===
    first_finalized_date = fields.Datetime(related='supplier_id.first_finalized_date')
    first_finalized_user_id = fields.Many2one(related='supplier_id.first_finalized_user_id')
    first_finalized_comment = fields.Text(related='supplier_id.first_finalized_comment')

    finalized_date = fields.Datetime(string='Finalized (datetime)')
    finalized_user_id = fields.Many2one(
        'res.users',
        string='Finalized (user)'
    )
    finalized_comment = fields.Text(string='Finalized (comment)')

    # === COMPUTED FIELDS === #
    is_contacted_editable = fields.Boolean(compute='_compute_editable_fields')
    is_finalized_editable = fields.Boolean(compute='_compute_editable_fields')

    # === DEFAULT === #
    @api.depends('contacted_date', 'finalized_date')
    def _compute_editable_fields(self):
        for rec in self:
            supplier = rec.supplier_id

            rec.is_contacted_editable = supplier.on_route_to_user_end_date
            rec.is_finalized_editable = supplier.contacted_date

    # === METHODS ONCHANGE === #
    @api.onchange('stage_selected')
    def _onchange_stage(self):
        if self.stage_selected == 'arrived':
            self.on_route_to_user_end_date = self.supplier_id.on_route_to_user_end_date
            self.on_route_to_end_user_id = self.supplier_id.on_route_to_end_user_id
            self.on_route_to_end_comment = self.supplier_id.on_route_to_end_comment

        elif self.stage_selected == 'contacted':
            self.contacted_date = self.supplier_id.contacted_date
            self.contacted_user_id = self.supplier_id.contacted_user_id
            self.contacted_comment = self.supplier_id.contacted_comment

        elif self.stage_selected == 'finalized':
            self.finalized_date = self.supplier_id.finalized_date
            self.finalized_user_id = self.supplier_id.finalized_user_id
            self.finalized_comment = self.supplier_id.finalized_comment

    # Arrived
    @api.onchange('on_route_to_user_end_date')
    def _onchange_on_route_to_user_end_date(self):

        if not self.on_route_to_user_end_date:
            return

        if (self.event_id.event_date and self.on_route_to_user_end_date <= self.event_id.event_date):
            return {
                'warning': {
                    'title': _('Arrived: Invalid datetime'),
                    'message': _(
                        'The date and time of Arrived (%s) is less than or equal to '
                        'the date and time of the event (%s)'
                    ) % (
                        self._format_datetime_tz(self.on_route_to_user_end_date),
                        self._format_datetime_tz(self.event_id.event_date)
                    )
                }
            }

        if (self.supplier_id.assignation_date and self.on_route_to_user_end_date <= self.supplier_id.assignation_date):
            return {
                'warning': {
                    'title': _('Arrived: Invalid datetime'),
                    'message': _(
                        'The date and time of Arrived (%s) is less than or equal to '
                        'the date and time of the Assigned (%s)'
                    ) % (
                        self._format_datetime_tz(self.on_route_to_user_end_date),
                        self._format_datetime_tz(self.supplier_id.assignation_date)
                    )
                }
            }

        if (self.on_route_to_user_end_date != self.supplier_id.on_route_to_user_end_date):
            self.on_route_to_end_user_id = self.env.user.id
            self.on_route_to_end_comment = False

    # Contacted
    @api.onchange('contacted_date')
    def _onchange_contacted_date(self):

        if not self.contacted_date:
            return

        if (self.event_id.event_date and self.contacted_date <= self.event_id.event_date):
            return {
                'warning': {
                    'title': _('Contacted: Invalid datetime'),
                    'message': _(
                        'The date and time of Contacted (%s) is less than or equal to '
                        'the date and time of the event (%s)'
                    ) % (
                        self._format_datetime_tz(self.contacted_date), self._format_datetime_tz(self.event_id.event_date)
                    )
                }
            }

        if (self.supplier_id.on_route_to_user_end_date and self.contacted_date <= self.supplier_id.on_route_to_user_end_date):
            return {
                'warning': {
                    'title': _('Contacted: Invalid datetime'),
                    'message': _(
                        'The date and time of Contacted (%s) is less than or equal to '
                        'the date and time of the Arrived (%s)'
                    ) % (
                        self._format_datetime_tz(self.contacted_date),
                        self._format_datetime_tz(self.supplier_id.on_route_to_user_end_date)
                    )
                }
            }

        if (self.contacted_date != self.supplier_id.contacted_date):
            self.contacted_user_id = self.env.user.id
            self.contacted_comment = False

    # Finalized
    @api.onchange('finalized_date')
    def _onchange_finalized_date(self):
        if not self.finalized_date:
            return

        if (self.event_id.event_date and self.finalized_date <= self.event_id.event_date):
            return {
                'warning': {
                    'title': _('Finalized: Invalid datetime'),
                    'message': _(
                        'The date and time of Finalized (%s) is less than or equal to '
                        'the date and time of the event (%s)'
                    ) % (
                        self._format_datetime_tz(self.finalized_date),
                        self._format_datetime_tz(self.event_id.event_date)
                    )
                }
            }

        if (self.supplier_id.contacted_date and self.finalized_date <= self.supplier_id.contacted_date):
            return {
                'warning': {
                    'title': _('Finalized: Invalid datetime'),
                    'message': _(
                        'The date and time of Finalized (%s) is less than or equal to '
                        'the date and time of the Contacted (%s)'
                    ) % (
                        self._format_datetime_tz(self.finalized_date),
                        self._format_datetime_tz(self.supplier_id.contacted_date))
                }
            }

        if (self.finalized_date != self.supplier_id.finalized_date):
            self.finalized_user_id = self.env.user.id
            self.finalized_comment = False

    # === ACTION === #
    def action_confirm(self):
        self.ensure_one()
        if not self.stage_selected:
            raise ValidationError(_('Please select a stage.'))

        supplier = self.supplier_id
        vals = {}

        if self.stage_selected == 'arrived':
            if self.on_route_to_user_end_date <= self.event_id.event_date:
                event_date = fields.Datetime.context_timestamp(self, self.event_id.event_date).strftime('%d-%m-%Y %H:%M:%S')
                raise ValidationError(_('Arrived date cannot be earlier than or equal to event date (%s)', event_date))
            else:
                self._action_on_route(
                    supplier,
                    vals,
                    self.on_route_to_user_end_date - timedelta(seconds=1),
                    self.on_route_to_end_user_id.id,
                    f'{supplier.display_name} - {self.on_route_to_user_end_date - timedelta(seconds=1)}'
                )

                self._action_arrived(
                    supplier,
                    vals,
                    self.on_route_to_user_end_date,
                    self.env.user.id,
                    self.on_route_to_end_comment
                )

        elif self.stage_selected == 'contacted':
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

        elif self.stage_selected == 'finalized':
            if self.finalized_date <= self.event_id.event_date:
                event_date = fields.Datetime.context_timestamp(self, self.event_id.event_date).strftime('%d-%m-%Y %H:%M:%S')
                raise ValidationError(_('Finalized date cannot be earlier than or equal to event date (%s)', event_date))
            else:
                self._action_on_route_2(
                    supplier,
                    vals,
                    self.finalized_date - timedelta(seconds=2),
                    self.finalized_user_id.id,
                    f'{supplier.display_name} - {self.finalized_date - timedelta(seconds=2)}'
                )

                self._action_arrived_2(
                    supplier,
                    vals,
                    self.finalized_date - timedelta(seconds=1),
                    self.finalized_user_id.id,
                    f'{supplier.display_name} - {self.finalized_date - timedelta(seconds=1)}'
                )

                self._action_finalized(
                    supplier,
                    vals,
                    self.finalized_date,
                    self.finalized_user_id.id,
                    self.finalized_comment
                )

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

    def _format_datetime_tz(self, dt):
        if not dt:
            return ''
        local_dt = fields.Datetime.context_timestamp(self, dt)
        return local_dt.strftime('%Y-%m-%d %H:%M:%S')

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
