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

    supplier_assignation_user_id = fields.Many2one(related='supplier_id.assignation_user_id')
    supplier_on_route_to_start_user_id = fields.Many2one(related='supplier_id.on_route_to_start_user_id')
    supplier_on_route_to_end_user_id = fields.Many2one(related='supplier_id.on_route_to_end_user_id')
    supplier_contacted_user_id = fields.Many2one(related='supplier_id.contacted_user_id')
    supplier_on_route_to_destination_start_user_id = fields.Many2one(related='supplier_id.on_route_to_destination_start_user_id')
    supplier_on_route_to_destination_end_user_id = fields.Many2one(related='supplier_id.on_route_to_destination_end_user_id')
    supplier_finalized_user_id = fields.Many2one(related='supplier_id.finalized_user_id')

    stage_selected_id = fields.Many2one(
        'ike.service.stage',
        string="New state",
        domain=[('ref', 'in', ['arrived', 'contacted', 'finalized'])])

    # === FIELDS STAGE === #
    # === ASSIGNED ===
    first_assignation_date = fields.Datetime(related='supplier_id.first_assignation_date')
    first_assignation_user_id = fields.Many2one(related='supplier_id.first_assignation_user_id')
    first_assignation_comment = fields.Text(related='supplier_id.first_assignation_comment')

    assignation_date = fields.Datetime(string='Assigned')
    assignation_user_id = fields.Many2one(
        'res.users',
        string='Assigned (user)',
        default=lambda self: self.env.user
    )
    assignation_comment = fields.Text(string='Assigned')

    # === ON ROUTE ===
    first_on_route_to_user_start_date = fields.Datetime(related='supplier_id.first_on_route_to_user_start_date')
    first_on_route_to_start_user_id = fields.Many2one(related='supplier_id.first_on_route_to_start_user_id')
    first_on_route_to_start_comment = fields.Text(related='supplier_id.first_on_route_to_start_comment')

    on_route_to_user_start_date = fields.Datetime(string='On route')
    on_route_to_start_user_id = fields.Many2one(
        'res.users',
        string='On route (user)',
        default=lambda self: self.env.user
    )
    on_route_to_start_comment = fields.Text(string='On route')

    # === ARRIVED ===
    first_on_route_to_user_end_date = fields.Datetime(related='supplier_id.first_on_route_to_user_end_date')
    first_on_route_to_end_user_id = fields.Many2one(related='supplier_id.first_on_route_to_end_user_id')
    first_on_route_to_end_comment = fields.Text(related='supplier_id.first_on_route_to_end_comment')

    on_route_to_user_end_date = fields.Datetime(string='Arrived')
    on_route_to_end_user_id = fields.Many2one(
        'res.users',
        string='Arrived (user)',
        default=lambda self: self.env.user
    )
    on_route_to_end_comment = fields.Text(string='Arrived')

    # === CONTACTED ===
    first_contacted_date = fields.Datetime(related='supplier_id.first_contacted_date')
    first_contacted_user_id = fields.Many2one(related='supplier_id.first_contacted_user_id')
    first_contacted_comment = fields.Text(related='supplier_id.first_contacted_comment')

    contacted_date = fields.Datetime(string='Contacted')
    contacted_user_id = fields.Many2one(
        'res.users',
        string='Contacted (user)',
        default=lambda self: self.env.user
    )
    contacted_comment = fields.Text(string='Contacted')

    # === ROUTE TO DESTINATION ===
    first_on_route_to_destination_start_date = fields.Datetime(related='supplier_id.first_on_route_to_destination_start_date')
    first_on_route_to_destination_start_user_id = fields.Many2one(related='supplier_id.first_on_route_to_destination_start_user_id')
    first_on_route_to_destination_start_comment = fields.Text(related='supplier_id.first_on_route_to_destination_start_comment')

    on_route_to_destination_start_date = fields.Datetime(string='Route to destination')
    on_route_to_destination_start_user_id = fields.Many2one(
        'res.users',
        string='Route to destination (user)',
        default=lambda self: self.env.user
    )
    on_route_to_destination_start_comment = fields.Text(string='Route to destination')

    # === HE ARRIVED DESTINATION ===
    first_on_route_to_destination_end_date = fields.Datetime(related='supplier_id.first_on_route_to_destination_end_date')
    first_on_route_to_destination_end_user_id = fields.Many2one(related='supplier_id.first_on_route_to_destination_end_user_id')
    first_on_route_to_destination_end_comment = fields.Text(related='supplier_id.first_on_route_to_destination_end_comment')

    on_route_to_destination_end_date = fields.Datetime(string='He arrived at his destination')
    on_route_to_destination_end_user_id = fields.Many2one(
        'res.users',
        string='He arrived at his destination (user)',
        default=lambda self: self.env.user
    )
    on_route_to_destination_end_comment = fields.Text(string='He arrived at his destination')

    # === FINALIZED ===
    first_finalized_date = fields.Datetime(related='supplier_id.first_finalized_date')
    first_finalized_user_id = fields.Many2one(related='supplier_id.first_finalized_user_id')
    first_finalized_comment = fields.Text(related='supplier_id.first_finalized_comment')

    finalized_date = fields.Datetime(string='Finalized')
    finalized_user_id = fields.Many2one(
        'res.users',
        string='Finalized (user)',
        default=lambda self: self.env.user
    )
    finalized_comment = fields.Text(string='Finalized')

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
        if self.assignation_date and not self.assignation_user_id:
            self.assignation_user_id = self.env.user
        if self.assignation_date != self._origin.assignation_date:
            self.assignation_comment = False

    # on rute
    @api.onchange('on_route_to_user_start_date')
    def _onchange_on_route_to_user_start_date(self):
        if self.on_route_to_user_start_date and not self.on_route_to_start_user_id:
            self.on_route_to_start_user_id = self.env.user
        if self.on_route_to_user_start_date != self._origin.on_route_to_user_start_date:
            self.on_route_to_start_comment = False
        if (
            self.on_route_to_user_start_date
            and self.assignation_date
            and self.on_route_to_user_start_date <= self.assignation_date
        ):
            self.on_route_to_user_start_date = False
            date = fields.Datetime.context_timestamp(self, self.assignation_date).strftime('%Y-%m-%d %H:%M:%S')
            return {'warning': {
                'title': _('Invalid date'),
                'message': _(
                    'On route date cannot be earlier than or equal to '
                    'Assigned date (%s).', date),
            }}

    # arrived
    @api.onchange('on_route_to_user_end_date')
    def _onchange_on_route_to_user_end_date(self):
        if self.on_route_to_user_end_date and not self.on_route_to_end_user_id:
            self.on_route_to_end_user_id = self.env.user
        if self.on_route_to_user_end_date != self._origin.on_route_to_user_end_date:
            self.on_route_to_end_comment = False
        if (
            self.on_route_to_user_end_date
            and self.on_route_to_user_start_date
            and self.on_route_to_user_end_date <= self.on_route_to_user_start_date
        ):
            self.on_route_to_user_end_date = False
            date = fields.Datetime.context_timestamp(self, self.on_route_to_user_start_date).strftime('%Y-%m-%d %H:%M:%S')
            return {'warning': {
                'title': _('Invalid date'),
                'message': _(
                    'Arrived date cannot be earlier than or equal to '
                    'On route date (%s).', date),
            }}

    # contacted
    @api.onchange('contacted_date')
    def _onchange_contacted_date(self):
        if self.contacted_date and not self.contacted_user_id:
            self.contacted_user_id = self.env.user
        if self.contacted_date != self._origin.contacted_date:
            self.contacted_comment = False
        if (
            self.contacted_date
            and self.on_route_to_user_end_date
            and self.contacted_date <= self.on_route_to_user_end_date
        ):
            self.contacted_date = False
            date = fields.Datetime.context_timestamp(self, self.on_route_to_user_end_date).strftime('%Y-%m-%d %H:%M:%S')
            return {'warning': {
                'title': _('Invalid date'),
                'message': _(
                    'Contacted date cannot be earlier than or equal to '
                    'Arrived date (%s).', date),
            }}

    # rute to destination
    @api.onchange('on_route_to_destination_start_date')
    def _onchange_on_route_to_destination_start_date(self):
        if self.on_route_to_destination_start_date and not self.on_route_to_destination_start_user_id:
            self.on_route_to_destination_start_user_id = self.env.user
        if self.on_route_to_destination_start_date != self._origin.on_route_to_destination_start_date:
            self.on_route_to_destination_start_comment = False

        if (
            self.on_route_to_destination_start_date
            and self.contacted_date
            and self.on_route_to_destination_start_date <= self.contacted_date
        ):
            self.on_route_to_destination_start_date = False
            date = fields.Datetime.context_timestamp(self, self.contacted_date).strftime('%Y-%m-%d %H:%M:%S')
            return {'warning': {
                'title': _('Invalid date'),
                'message': _(
                    'On route to destination date cannot be earlier than or equal to '
                    'Contacted date (%s).', date),
            }}

    # he arrived destination
    @api.onchange('on_route_to_destination_end_date')
    def _onchange_on_route_to_destination_end_date(self):
        if self.on_route_to_destination_end_date and not self.on_route_to_destination_end_user_id:
            self.on_route_to_destination_end_user_id = self.env.user
        if self.on_route_to_destination_end_date != self._origin.on_route_to_destination_end_date:
            self.on_route_to_destination_end_comment = False
        if (
            self.on_route_to_destination_end_date
            and self.on_route_to_destination_start_date
            and self.on_route_to_destination_end_date <= self.on_route_to_destination_start_date
        ):
            self.on_route_to_destination_end_date = False
            date = fields.Datetime.context_timestamp(self, self.on_route_to_destination_start_date).strftime('%Y-%m-%d %H:%M:%S')
            return {'warning': {
                'title': _('Invalid date'),
                'message': _(
                    'Arrived at destination date cannot be earlier than or equal to '
                    'On route to destination date (%s).', date),
            }}

    # finalized
    @api.onchange('finalized_date')
    def _onchange_finalized_date(self):
        if self.finalized_date and not self.finalized_user_id:
            self.finalized_user_id = self.env.user
        if self.finalized_date != self._origin.finalized_date:
            self.finalized_comment = False
        if (
            self.finalized_date
            and self.on_route_to_destination_end_date
            and self.finalized_date <= self.on_route_to_destination_end_date
        ):
            self.finalized_date = False
            date = fields.Datetime.context_timestamp(self, self.on_route_to_destination_end_date).strftime('%Y-%m-%d %H:%M:%S')
            return {'warning': {
                'title': _('Invalid date'),
                'message': _(
                    'Finalized date cannot be earlier than or equal to '
                    'Arrived at destination date (%s).', date),
            }}

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

        if not vals:
            raise ValidationError(_('Invalid stage.'))

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
        vals.update({
            'assignation_date': datetime,
            'assignation_user_id': user,
            'assignation_comment': comment,
        })
        if not supplier.first_assignation_date:
            vals.update({
                'first_assignation_date': datetime or fields.Datetime.now(),
                'first_assignation_user_id': user,
                'first_assignation_comment': comment,
            })
        supplier.action_assign()

    def _action_on_route(self, supplier, vals, datetime, user, comment):
        vals.update({
            'on_route_to_user_start_date': datetime,
            'on_route_to_start_user_id': user,
            'on_route_to_start_comment': comment,
        })
        if not supplier.first_on_route_to_user_start_date:
            vals.update({
                'first_on_route_to_user_start_date': datetime or fields.Datetime.now(),
                'first_on_route_to_start_user_id': user,
                'first_on_route_to_start_comment': comment,
            })

        supplier.action_on_route()

    def _action_arrived(self, supplier, vals, datetime, user, comment):
        vals.update({
            'on_route_to_user_end_date': datetime,
            'on_route_to_end_user_id': user,
            'on_route_to_end_comment': comment,
        })
        if not supplier.first_on_route_to_user_end_date:
            vals.update({
                'first_on_route_to_user_end_date': datetime or fields.Datetime.now(),
                'first_on_route_to_end_user_id': user,
                'first_on_route_to_end_comment': comment,
            })

        supplier.action_arrive()

    def _action_contacted(self, supplier, vals, datetime, user, comment):
        vals.update({
            'contacted_date': datetime,
            'contacted_user_id': user,
            'contacted_comment': comment,
        })
        if not supplier.first_contacted_date:
            vals.update({
                'first_contacted_date': datetime or fields.Datetime.now(),
                'first_contacted_user_id': user,
                'first_contacted_comment': comment,
            })

        supplier.action_contact()

    def _action_on_route_2(self, supplier, vals, datetime, user, comment):
        vals.update({
            'on_route_to_destination_start_date': datetime,
            'on_route_to_destination_start_user_id': user,
            'on_route_to_destination_start_comment': comment,
        })
        if not supplier.first_on_route_to_destination_start_date:
            vals.update({
                'first_on_route_to_destination_start_date': datetime or fields.Datetime.now(),
                'first_on_route_to_destination_start_user_id': user,
                'first_on_route_to_destination_start_comment': comment,
            })

        supplier.action_on_route_to_the_destination()

    def _action_arrived_2(self, supplier, vals, datetime, user, comment):
        vals.update({
            'on_route_to_destination_end_date': datetime,
            'on_route_to_destination_end_user_id': user,
            'on_route_to_destination_end_comment': comment,
        })
        if not supplier.first_on_route_to_destination_end_date:
            vals.update({
                'first_on_route_to_destination_end_date': datetime or fields.Datetime.now(),
                'first_on_route_to_destination_end_user_id': user,
                'first_on_route_to_destination_end_comment': comment,
            })
        supplier.action_arrive_to_the_destination()

    def _action_finalized(self, supplier, vals, datetime, user, comment):
        vals.update({
            'finalized_date': datetime,
            'finalized_user_id': user,
            'finalized_comment': comment,
        })
        if not supplier.first_finalized_date:
            vals.update({
                'first_finalized_date': datetime or fields.Datetime.now(),
                'first_finalized_user_id': user,
                'first_finalized_comment': comment,
            })

        supplier.action_finalize()
