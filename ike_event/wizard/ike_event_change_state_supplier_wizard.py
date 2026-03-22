from odoo import models, fields, api, _


class IkeEventChangeStateSupplierWizard(models.TransientModel):
    _name = 'ike.event.change.state.supplier.wizard'
    _description = 'Event Change State Wizard'

    # === FIELDS SUPPLIER === #
    event_id = fields.Many2one('ike.event', required=True, readonly=True)
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        required=True,
        readonly=True,
        domain="[('x_is_supplier','=',True)]"
    )
    supplier_number = fields.Integer(required=True, readonly=True)
    stage_id = fields.Many2one('ike.service.stage', string="Current state")

    # === FIELDS NEW STAGE === #
    new_stage_domain = fields.Binary(compute='_compute_new_stage_domain')
    new_stage_id = fields.Many2one('ike.service.stage', string="New state")
    user_id = fields.Many2one('res.users', string='User', default=lambda self: self.env.user)

    # === FIELDS DATE OF STATUS CHANGE === #
    assigned_date = fields.Datetime(string='Datetime (Assigned)')
    on_route_date = fields.Datetime(string='Datetime (On Route)')
    arrived_date = fields.Datetime(string='Datetime (Arrived)')
    contacted_date = fields.Datetime(string='Datetime (Contacted)')
    on_route_2_date = fields.Datetime(string='Datetime (Route to destination)')
    arrived_2_date = fields.Datetime(string='Datetime (He arrived at his destination)')
    finalized_date = fields.Datetime(string='Datetime (Finalized)')

    # === COMPUTED FIELDS === #
    show_assigned = fields.Boolean(compute='_compute_show_fields')
    show_on_route = fields.Boolean(compute='_compute_show_fields')
    show_arrived = fields.Boolean(compute='_compute_show_fields')
    show_contacted = fields.Boolean(compute='_compute_show_fields')
    show_on_route_2 = fields.Boolean(compute='_compute_show_fields')
    show_arrived_2 = fields.Boolean(compute='_compute_show_fields')
    show_finalized = fields.Boolean(compute='_compute_show_fields')

    STAGE_SEQUENCE = [
        'assigned', 'on_route', 'arrived',
        'contacted', 'on_route_2', 'arrived_2', 'finalized',
    ]

    # === METHODS COMPUTE === #
    @api.depends('stage_id')
    def _compute_new_stage_domain(self):
        stage_sequence = ['preparing'] + self.STAGE_SEQUENCE + ['cancel']
        for rec in self:
            try:
                current_index = stage_sequence.index(rec.stage_id.ref) if rec.stage_id else 0
                allowed_refs = stage_sequence[current_index + 1:-1]
            except ValueError:
                allowed_refs = stage_sequence[1:-1]
            rec.new_stage_domain = [('active', '=', True), ('ref', 'in', allowed_refs)]

    @api.depends('stage_id', 'new_stage_id')
    def _compute_show_fields(self):
        for rec in self:
            visible = set()
            if rec.stage_id and rec.new_stage_id:
                try:
                    start = self.STAGE_SEQUENCE.index(rec.stage_id.ref) + 1
                    end = self.STAGE_SEQUENCE.index(rec.new_stage_id.ref) + 1
                    visible = set(self.STAGE_SEQUENCE[start:end])
                except ValueError:
                    pass
            rec.show_assigned = 'assigned' in visible
            rec.show_on_route = 'on_route' in visible
            rec.show_arrived = 'arrived' in visible
            rec.show_contacted = 'contacted' in visible
            rec.show_on_route_2 = 'on_route_2' in visible
            rec.show_arrived_2 = 'arrived_2' in visible
            rec.show_finalized = 'finalized' in visible

    # === ACTIONS === #
    def action_confirm(self):
        self.ensure_one()
        supplier = self.env['ike.event.supplier'].search([
            ('event_id', '=', self.event_id.id),
            ('supplier_id', '=', self.supplier_id.id),
            ('supplier_number', '=', self.supplier_number),
            ('selected', '=', True)
        ], limit=1)

        if not supplier:
            return

        stage_map = {
            'assigned': (
                'assignation_date',
                None,
                self.assigned_date,
                supplier.action_assign
            ),
            'on_route': (
                'on_route_to_user_start_date',
                'on_route_to_start_user_id',
                self.on_route_date,
                supplier.action_on_route
            ),
            'arrived': (
                'on_route_to_user_end_date',
                'on_route_to_end_user_id',
                self.arrived_date,
                supplier.action_arrive
            ),
            'contacted': (
                'contacted_date',
                'contacted_user_id',
                self.contacted_date,
                supplier.action_contact
            ),
            'on_route_2': (
                'on_route_to_destination_start_date',
                'on_route_to_destination_start_user_id',
                self.on_route_2_date,
                supplier.action_on_route_to_the_destination
            ),
            'arrived_2': (
                'on_route_to_destination_end_date',
                'on_route_to_destination_end_user_id',
                self.arrived_2_date,
                supplier.action_arrive_to_the_destination
            ),
            'finalized': (
                'finalized_date',
                'finalized_user_id',
                self.finalized_date,
                supplier.action_finalize
            ),
        }

        target = self.new_stage_id.ref
        data = stage_map.get(target)

        if not data:
            return

        date_field, user_field, wizard_date, action = data

        date_value = wizard_date or fields.Datetime.now()

        if not getattr(supplier, date_field):
            setattr(supplier, date_field, date_value)

        if user_field and not getattr(supplier, user_field):
            setattr(supplier, user_field, self.env.user.id)

        action()
