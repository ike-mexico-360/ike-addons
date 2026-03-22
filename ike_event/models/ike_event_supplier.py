# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError


class IkeEventSupplier(models.Model):
    _name = 'ike.event.supplier'
    _inherit = ['ike.event.supplier.base', 'mail.thread', 'mail.tracking.duration.mixin']
    _description = 'Event Supplier'
    _track_duration_field = 'stage_id'
    _order = 'search_number desc, sequence'

    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', "Note"),
    ], default=False)

    # Related Fields
    event_search_number = fields.Integer(related='event_id.supplier_search_number', string='Search Number (Event)')
    destination_duration = fields.Float(related="event_id.destination_duration")

    # Search fields
    supplier_number = fields.Integer(default=1, required=True)
    search_number = fields.Integer(default=1, required=True)
    estimated_distance = fields.Float(help='Estimated distance to reach the user, in kilometers.', default=0.0)
    estimated_duration = fields.Float(help='Estimated duration to arrive to the user, in minutes.', default=0.0)
    estimated_cost = fields.Float(related='supplier_link_id.estimated_cost', store=True, readonly=False)

    # Assignation supplier fields
    ranking = fields.Integer(string='Ranking', default=0, readonly=True)
    supplier_phone = fields.Char(related='supplier_id.phone', string='Phone')
    assigned = fields.Char(string='Operator')
    latitude = fields.Char(copy=False)
    longitude = fields.Char(copy=False)
    route = fields.Json(copy=False)

    # === AUTHORIZATION FIELDS === #
    type_authorization_id = fields.Many2one(related='supplier_link_id.type_authorization_id', readonly=False)
    reason_authorizer_id = fields.Many2one(related='supplier_link_id.reason_authorizer_id', readonly=False)
    authorization_by_nu = fields.Boolean(related='supplier_link_id.authorization_by_nu', string='Is Authorized By Nu', readonly=False)
    authorizer_id = fields.Many2one(related='supplier_link_id.authorizer_id', readonly=False)
    authorizer_domain = fields.Binary(compute="_compute_authorizer_domain")
    nu_user_id = fields.Many2one(related='event_id.user_id')

    # === EVIDENCE FIELDS === #
    service_evidence_ids = fields.One2many('ike.event.evidence', 'event_supplier_id', string='Evidence')

    # === SERVICE FIELDS === #
    subservice_id = fields.Many2one('product.product', related='event_id.sub_service_id', store=False)
    event_supplier_summary_data = fields.Html(compute='_compute_event_supplier_summary_data')
    travel_tracking_url = fields.Char(compute='_compute_travel_tracking_url')
    # === STAGED LINE PROGRESS FIELDS === #
    on_route_to_user_start_date_widget = fields.Datetime()
    on_route_to_user_end_date_widget = fields.Datetime()
    on_route_to_destination_start_date_widget = fields.Datetime()
    on_route_to_destination_end_date_widget = fields.Datetime()

    on_route_to_user_start_date = fields.Datetime()
    on_route_to_start_user_id = fields.Many2one('res.users', 'In route user', readonly=True, tracking=True)
    on_route_to_user_end_date = fields.Datetime()
    on_route_to_end_user_id = fields.Many2one('res.users', 'Arrive user', readonly=True, tracking=True)
    on_route_to_destination_start_date = fields.Datetime()
    on_route_to_destination_start_user_id = fields.Many2one('res.users', 'In route to destination user', readonly=True, tracking=True)
    on_route_to_destination_end_date = fields.Datetime()
    on_route_to_destination_end_user_id = fields.Many2one(
        'res.users',
        'He arrived at his destination user',
        readonly=True,
        tracking=True)
    travel_progress_percent = fields.Float(string="Travel Progress (%)")

    # === DETAILS FIELDS === #
    supplier_link_id = fields.Many2one('ike.event.supplier.link')
    supplier_product_ids = fields.One2many(related='supplier_link_id.supplier_product_ids', readonly=False)
    amount_concept_subtotal = fields.Float(related='supplier_link_id.amount_concept_subtotal', string='Subtotal')
    amount_concept_vat = fields.Float(related='supplier_link_id.amount_concept_vat', string='VAT')
    amount_concept_total = fields.Float(related='supplier_link_id.amount_concept_total', string='Total')

    # === COMPUTES === #
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.supplier_id.name}, {rec.name}'

    @api.depends('type_authorization_id', 'authorizer_id')
    def _compute_authorizer_domain(self):
        for rec in self:
            domain = []
            if rec.type_authorization_id.is_client:
                client_ids = self.env['res.partner'].search([
                    ('is_company', '=', True),
                    ('x_is_client', '=', True)
                ])
                domain = [('disabled', '=', False), ('id', 'in', client_ids.ids)]
            if rec.type_authorization_id.is_user_internal:
                user_internal_ids = self.env['res.users'].search([
                    ('share', '=', False),
                ]).mapped("partner_id")
                domain = [('disabled', '=', False), ('id', 'in', user_internal_ids.ids)]
            rec.authorizer_domain = domain

    @api.depends('supplier_id', 'truck_id', 'event_id')
    def _compute_travel_tracking_url(self):
        for rec in self:
            travel_tracking_url_base = self.env['ir.config_parameter'].sudo().get_param('ike_event.travel_tracking_url_base')
            travel_tracking_url = '%s/?vehicle_id=%s&service_id=%s&db=%s&showonlytab=live' % (
                travel_tracking_url_base or 'https://www.example.com', rec.truck_id.x_vehicle_ref, rec.event_id.id, self.env.cr.dbname
            )
            rec.travel_tracking_url = travel_tracking_url

    @api.depends('event_id.service_res_id')
    def _compute_event_supplier_summary_data(self):
        for rec in self:
            event_summary_supplier_data = ""
            states = ('searching', 'assigned', 'in_progress', 'completed', 'cancel')
            if rec.event_id.service_ref == 'vial' and rec.event_id.stage_ref in states:
                # Modelo de detalles del vehículo al que se le dará el servicio
                vial_res_model = rec.event_id.service_res_model
                vial_res_id = rec.event_id.service_res_id
                vial_record = self.env[vial_res_model].browse(vial_res_id)

                # Confirmed service section
                event_summary_supplier_data = "<h3>%s</h3>" % _('Confirmed service')
                user_service_fields = [
                    'vehicle_brand',
                    'vehicle_model',
                    'vehicle_year',
                    'vehicle_category_id',
                    'vehicle_plate',
                    'vehicle_color',
                ]
                vial_record_fields = vial_record.fields_get(user_service_fields)
                vial_record_data = vial_record.read(user_service_fields)[0]
                if vial_record:  # Omitir si no hay registro
                    for field in user_service_fields:  # Vehicle details
                        value = vial_record_data[field] or ''
                        if vial_record_fields[field]['type'] == 'many2one' and value:
                            value = value[1]
                        event_summary_supplier_data += f"""
                            <div><span style='font-weight: bold;'>{vial_record_fields[field]['string']}: </span>
                            <span>{value}</span></div>
                        """

                # Location section
                location_fields = ['location_label', 'destination_label', 'destination_distance']
                location_record_fields = rec.event_id.fields_get(location_fields)
                location_record_data = rec.event_id.read(location_fields)[0]
                for field in location_fields:  # Location details
                    if field == 'destination_distance':  # Formatear distancia
                        location_record_data[field] = f"{round(location_record_data[field], 3)} km"
                    event_summary_supplier_data += f"""
                        <div><span style='font-weight: bold;'>{location_record_fields[field]['string']}: </span>
                        <span>{location_record_data[field] or ''}</span></div>
                    """

                # Supplier section
                event_summary_supplier_data += "<h3 class='mt-3'>%s</h3>" % _('Assigned supplier')

                supplier_fields = ['supplier_id', 'assigned', 'estimated_duration', 'assignation_type', 'truck_id', 'truck_plate']
                supplier_record_fields = rec.fields_get(supplier_fields)
                supplier_record_data = rec.read(supplier_fields)[0]

                # Estimated duration to destination
                # Insertar clave 'estimated_duration_destination' después de 'estimated_duration' y calcular
                fe_index = supplier_fields.index('estimated_duration') + 1
                supplier_fields.insert(fe_index, 'estimated_duration_destination')
                supplier_record_fields['estimated_duration_destination'] = {'string': _('Estimated Duration Destination')}
                # Simular campo virtual
                estimated_duration_destination_minutes, estimated_duration_destination_seconds =\
                    self.decimal_minutes_to_time(rec.event_id.destination_duration)
                supplier_record_data['estimated_duration_destination'] = (
                    "%s minutes %s seconds" % (estimated_duration_destination_minutes, estimated_duration_destination_seconds))

                if rec.acceptance_date and rec.event_id.supplier_search_date:
                    # Assignation Duration
                    # Insertar clave 'assignation_duration' después de 'assignation_type' y calcular
                    f_index = supplier_fields.index('assignation_type') + 1
                    supplier_fields.insert(f_index, 'assignation_duration')
                    supplier_record_fields['assignation_duration'] = {'string': _('Assignation Duration')}

                    # Assignation Duration (Bloque que tiene Nefta en ike_event_summary)
                    # ToDo FIX rec.event_id.supplier_search_date
                    # -------------------------
                    if not rec.event_id.supplier_search_date:  # Remove
                        rec.event_id.supplier_search_date = fields.Datetime.now()  # Remove
                    # -------------------------
                    delta = rec.acceptance_date - rec.event_id.supplier_search_date
                    # -------------------------
                    duration = int(delta.total_seconds())
                    # Convert seconds to 'X minutes X seconds'
                    # assignation_duration = str(duration) + "s"
                    assignation_minutes = duration // 60
                    assignation_seconds = duration % 60
                    assignation_duration = _("%s minutes %s seconds") % (assignation_minutes, assignation_seconds)

                    supplier_record_data['assignation_duration'] = assignation_duration

                for field in supplier_fields:
                    # Obtener display_name de los many2one
                    if field in ['supplier_id', 'truck_id']:
                        field_data = supplier_record_data.get(field, False)
                        if field_data:
                            supplier_record_data[field] = supplier_record_data[field][1]
                        else:
                            supplier_record_data[field] = ''
                    if field == 'assigned':  # Hack, cambiar etiqueta para que tome la traducción anterior
                        supplier_record_fields[field]['string'] = _('Operator')
                    if field == 'estimated_duration':
                        estimated_duration_minutes, estimated_duration_seconds =\
                            self.decimal_minutes_to_time(supplier_record_data[field])
                        supplier_record_data[field] = (
                            "%s minutes %s seconds" % (estimated_duration_minutes, estimated_duration_seconds))
                    if field == 'assignation_type':
                        assignation_types = dict(rec._fields['assignation_type'].get_description(self.env)['selection'])
                        supplier_record_data[field] = assignation_types.get(supplier_record_data[field])
                    if field == 'vehicle_plate':  # Hack, cambiar etiqueta para que tome la traducción anterior
                        supplier_record_fields[field]['string'] = _('Plate')
                    event_summary_supplier_data += f"""
                        <div><span style='font-weight: bold;'>{supplier_record_fields[field]['string']}: </span>
                        <span>{supplier_record_data[field] or ''}</span></div>
                    """

            rec.event_supplier_summary_data = event_summary_supplier_data

    # === DEFAULT === #
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        preparing_stage = self.env.ref("ike_event.ike_service_stage_preparing")
        res["stage_id"] = preparing_stage.id
        return res

    # === ONCHANGE === #
    @api.onchange('type_authorization_id')
    def onchange_type_authorization_id(self):
        if self.type_authorization_id.id != self._origin.type_authorization_id.id:
            self.authorizer_id = False
        self.authorization_by_nu = False if not self.type_authorization_id.is_nu else True

    # === ACTIONS === #
    def action_request_authorization(self):
        self.supplier_link_id.sudo().action_request_authorization()

    def action_accept_authorization(self):
        self.supplier_link_id.sudo().action_accept_authorization()

    def action_reject_authorization(self):
        self.supplier_link_id.sudo().action_reject_authorization()

    # == STAGE ACTIONS == #
    def action_assign(self):
        assign_stage = self.env.ref('ike_event.ike_service_stage_assigned')
        for rec in self:
            rec.stage_id = assign_stage.id

    def action_on_route(self):
        supplier_on_route_stage = self.env.ref('ike_event.ike_service_stage_on_route')
        event_stage_assigned = self.env.ref('ike_event.ike_event_stage_assigned')
        for rec in self:
            rec.stage_id = supplier_on_route_stage.id
            rec.on_route_to_user_start_date_widget = fields.Datetime.now()
            # Si el evento aún está en etapa asignado, se puede pasar a la etapa en ruta
            if rec.event_id.stage_ref == event_stage_assigned.ref and rec.event_id.step_number == 1:
                rec.event_id.action_forward()
                rec.broadcastReload(event_reload=True)

    def action_arrive(self):
        arrived_stage = self.env.ref('ike_event.ike_service_stage_arrived')
        for rec in self:
            rec.stage_id = arrived_stage.id
            rec.on_route_to_user_end_date_widget = fields.Datetime.now()

    def action_contact(self):
        contacted_stage = self.env.ref('ike_event.ike_service_stage_contacted')
        for rec in self:
            rec.stage_id = contacted_stage.id

    def action_on_route_to_the_destination(self):
        on_route_stage = self.env.ref('ike_event.ike_service_stage_on_route_2')
        for rec in self:
            rec.stage_id = on_route_stage.id
            rec.on_route_to_destination_start_date_widget = fields.Datetime.now()

    def action_arrive_to_the_destination(self):
        arrived_stage = self.env.ref('ike_event.ike_service_stage_arrived_2')
        for rec in self:
            rec.stage_id = arrived_stage.id
            rec.on_route_to_destination_end_date_widget = fields.Datetime.now()

    def action_finalize(self):
        supplier_finalized_stage = self.env.ref('ike_event.ike_service_stage_finalized')
        event_stage_in_progress = self.env.ref('ike_event.ike_event_stage_in_progress')
        for rec in self:
            rec.stage_id = supplier_finalized_stage.id
            # Vehicle State
            rec.truck_id.x_vehicle_service_state = 'available'
            # Concluir el evento, si es multi proveedor, concluir cuando todos estén finalizados
            if rec.event_id.stage_ref == event_stage_in_progress.ref and rec.event_id.step_number == 1:
                selected_suppliers = rec.event_id.service_supplier_ids.filtered(lambda x: x.state in ('accepted', 'assigned'))
                finalized_suppliers = []
                for selected_supplier in selected_suppliers:
                    if selected_supplier.stage_id.id == supplier_finalized_stage.id:
                        finalized_suppliers.append(True)
                    else:
                        finalized_suppliers.append(False)
                if all(finalized_suppliers):
                    rec.event_id.action_forward()
                    rec.broadcastReload(event_reload=True)

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

    # === ACTION VIEW === #
    def action_view_products(self):
        self.ensure_one()
        view_id = self.env.ref('ike_event.ike_event_supplier_link_form_view').id
        return {
            'name': self.supplier_id.display_name + " " + _('Concepts'),
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.supplier.link',
            'res_id': self.supplier_link_id.id,
            'views': [(view_id, 'form')],
            'context': {
                **self.env.context,
                'create': False,
                'edit': True,
                'from_add_concept': self.selected is True or self.is_manual and self.state == 'available'
            },
            'target': 'new',
        }

    def action_view_products_base_costs(self):
        self.ensure_one()
        view_id = self.env.ref('ike_event.ike_event_supplier_link_base_cots_form_view').id
        return {
            'name': self.supplier_id.display_name + " " + _('Concepts'),
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.supplier.link',
            'res_id': self.supplier_link_id.id,
            'views': [(view_id, 'form')],
            'context': {
                **self.env.context,
            },
            'target': 'new',
        }

    def action_view_ike_event_service_cost(self):
        list_view = self.env.ref('ike_event.ike_event_supplier_product_service_costs_list_view').id

        return {
            'name': _('Service costs'),
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.supplier.product',
            'view_mode': 'list',
            'views': [(list_view, 'list')],
            'search_view_id': False,
            'domain': [
                ('event_supplier_link_id', 'in', self.ids),
                ('display_type', 'not in', ['line_section', 'line_note']),
            ],
            'target': 'new',
            'context': {
                **self.env.context,
                'create': False,
                'edit': False,
            },
        }

    def action_open_travel_tracking(self):
        self.ensure_one()
        return {
            'name': 'Assigned supplier: %s' % self.supplier_id.name,
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.supplier',
            'view_mode': 'form',
            'views': [(self.env.ref('ike_event.view_ike_event_supplier_popup_form').id, 'form')],
            'target': 'new',
            'res_id': self.id,
            'context': {
                **self.env.context,
                'create': False,
                'edit': True,
            },
        }

    # === Auxiliary ===
    @staticmethod
    def decimal_minutes_to_time(decimal_minutes):
        minutes = int(decimal_minutes)
        seconds = round((decimal_minutes - minutes) * 60)
        return minutes, seconds


class IkeEventSupplierLink(models.Model):
    _name = 'ike.event.supplier.link'
    _description = 'Event Supplier Link'

    event_id = fields.Many2one('ike.event', required=True)
    supplier_id = fields.Many2one('res.partner', required=True, index=True, readonly=True)
    supplier_number = fields.Integer(required=True, readonly=True, default=1)

    estimated_cost = fields.Float(default=0.0, compute='_compute_estimated_cost', store=True)

    # === AUTHORIZATION FIELDS === #
    type_authorization_id = fields.Many2one('custom.additional.concept.authorizer.type')
    reason_authorizer_id = fields.Many2one('custom.reason.authorizing.additional.costs')
    authorizer_id = fields.Many2one('res.partner', string="Responsible Name")
    authorization_by_nu = fields.Boolean(related='type_authorization_id.is_nu')
    authorizer_domain = fields.Binary(compute="_compute_authorizer_domain")
    nu_user_id = fields.Many2one(related='event_id.user_id')
    authorizer = fields.Char('Authorizer', compute="_compute_authorizer_name", store=True)

    # === LINE FIELDS === #
    supplier_product_ids = fields.One2many('ike.event.supplier.product', 'event_supplier_link_id', string='Concepts')
    amount_concept_subtotal = fields.Float(string='Subtotal', compute='_compute_amount_supplier_product', store=True)
    amount_concept_vat = fields.Float(string='VAT', compute='_compute_amount_supplier_product', store=True)
    amount_concept_total = fields.Float(string='Total', compute='_compute_amount_supplier_product', store=True)

    base_amount_concept_subtotal = fields.Float(
        string='Agreement Subtotal', compute='_compute_base_amount_supplier_product', store=True)
    base_amount_concept_vat = fields.Float(
        string='Agreement VAT', compute='_compute_base_amount_supplier_product', store=True)
    base_amount_concept_total = fields.Float(
        string='Agreement Total', compute='_compute_base_amount_supplier_product', store=True)

    # === COMPUTED === #
    @api.depends('supplier_product_ids.subtotal', 'supplier_product_ids.vat')
    def _compute_amount_supplier_product(self):
        for rec in self:
            amount_subtotal = 0.0
            amount_total = 0.0
            amount_vat = 0.0

            for line in rec.supplier_product_ids:
                if not line.display_type:
                    amount_subtotal += line.cost_price
                    amount_vat += line.vat
                    amount_total = amount_subtotal + amount_vat

            rec.amount_concept_subtotal = amount_subtotal
            rec.amount_concept_vat = amount_vat
            rec.amount_concept_total = amount_total

    @api.depends('supplier_product_ids.base_subtotal', 'supplier_product_ids.base_vat')
    def _compute_base_amount_supplier_product(self):
        for rec in self:
            base_amount_subtotal = 0.0
            base_amount_total = 0.0
            base_amount_vat = 0.0

            for line in rec.supplier_product_ids:
                if not line.display_type:
                    base_amount_subtotal += line.base_cost_price
                    base_amount_vat += line.base_vat
                    base_amount_total = base_amount_subtotal + base_amount_vat

            rec.base_amount_concept_subtotal = base_amount_subtotal
            rec.base_amount_concept_vat = base_amount_vat
            rec.base_amount_concept_total = base_amount_total

    @api.depends('supplier_product_ids')
    def _compute_estimated_cost(self):
        for rec in self:
            subtotal = round(sum(rec.supplier_product_ids.mapped('cost_price') or []), 2)
            vat = round(sum(rec.supplier_product_ids.mapped('vat') or []), 2)
            rec.estimated_cost = round(subtotal + vat, 2)

    @api.depends('type_authorization_id', 'authorizer_id')
    def _compute_authorizer_domain(self):
        for rec in self:
            domain = []
            if rec.type_authorization_id.is_client:
                client_ids = self.env['res.partner'].search([
                    ('is_company', '=', True),
                    ('x_is_client', '=', True)
                ])
                domain = [('disabled', '=', False), ('id', 'in', client_ids.ids)]
            if rec.type_authorization_id.is_user_internal:
                user_internal_ids = self.env['res.users'].search([
                    ('share', '=', False),
                ]).mapped("partner_id")
                domain = [('disabled', '=', False), ('id', 'in', user_internal_ids.ids)]
            rec.authorizer_domain = domain

    @api.depends('type_authorization_id', 'authorization_by_nu', 'nu_user_id.name', 'authorizer_id.name')
    def _compute_authorizer_name(self):
        encryption_util = self.env['custom.encryption.utility']
        for rec in self:
            if rec.type_authorization_id and rec.authorization_by_nu:
                rec.authorizer = encryption_util.decrypt_aes256(rec.nu_user_id.name) or ''
            else:
                rec.authorizer = rec.authorizer_id.name or ''

    # === ONCHANGE === #
    @api.onchange('type_authorization_id')
    def onchange_type_authorization_id(self):
        if self.type_authorization_id.id != self._origin.type_authorization_id.id:
            self.authorizer_id = False
        self.authorization_by_nu = False if not self.type_authorization_id.is_nu else True

    # === ACTION === #
    def action_save_and_request_authorization(self):
        for rec in self:
            supplier = self.env['ike.event.supplier'].search([
                ('supplier_link_id', '=', rec.id)
            ], limit=1)

            if supplier:
                supplier.action_request_authorization()

        return True

    def action_request_authorization(self):
        self.ensure_one()
        # ToDo: Send notification?
        print("action_request_authorization")

    def action_accept_authorization(self):
        self.ensure_one()
        authorized_amount = self.event_id.previous_amount + self.event_id.current_amount
        authorizer = (
            self.nu_user_id.display_name
            if self.authorization_by_nu
            else self.authorizer_id.display_name
        )
        self.event_id.authorized_amount = authorized_amount
        event_authorization_id = self.env['ike.event.authorization'].create({
            'event_id': self.event_id.id,
            'supplier_id': self.supplier_id.id,
            'supplier_number': self.supplier_number,
            'authorized_amount': authorized_amount,
            'type_authorization_id': self.type_authorization_id.id,
            'reason_authorizer_id': self.reason_authorizer_id.id,
            'authorization_by_nu': self.authorization_by_nu,
            'authorizer_id': self.authorizer_id and self.authorizer_id.id,
            'authorizer': authorizer,
        })

        for product_id in self.supplier_product_ids:
            if product_id.authorization_pending:
                product_id.authorization_ids = [Command.create({
                    'event_authorization_id': event_authorization_id.id,
                    'quantity': product_id.quantity,
                    'unit_price': product_id.unit_price,
                    'amount': product_id.subtotal,
                })]
                product_id.authorization_pending = False

        # Start automatic notifications
        self.event_id.action_start_notifications()

    def action_reject_authorization(self):
        self.ensure_one()
        # ToDo: Reject?
        print("action_reject_authorization")

    def get_product_cost(self, product_id: int):
        supplier_id: int = self.supplier_id.id
        product_ids = [product_id]

        # Matrix Lines
        matrix_cost_line_ids = self.event_id.get_supplier_product_matrix_lines(supplier_id, product_ids)
        cost_line_id = matrix_cost_line_ids.filtered(
            lambda x:
                x.concept_id.id == product_id
                and x.supplier_status_id.ref == 'concluded')
        cancel_cost_line_id = matrix_cost_line_ids.filtered(
            lambda x:
                x.concept_id.id == product_id
                and x.supplier_status_id.ref == 'cancelled')

        return cost_line_id[0].cost if cost_line_id else 0, cancel_cost_line_id[0].cost if cancel_cost_line_id else 0


class IkeServiceStage(models.Model):
    _name = 'ike.service.stage'
    _description = 'Service Stage'
    _order = 'sequence, id'

    name = fields.Char(translate=True)
    ref = fields.Char()
    sequence = fields.Integer(default=1)
    color = fields.Char()
    fold = fields.Boolean(default=False)
    hide_timer = fields.Boolean(default=False)
    last_stage = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
