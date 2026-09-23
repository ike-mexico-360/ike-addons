# -*- coding: utf-8 -*-

import json

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression


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

    truck_domain = fields.Binary(compute='_compute_truck_domain')

    # Related Fields
    event_search_number = fields.Integer(related='event_id.supplier_search_number', string='Search Number (Event)')
    destination_duration = fields.Float(related="event_id.destination_duration")
    scheduled = fields.Boolean(related="event_id.scheduled")

    # Search fields
    supplier_number = fields.Integer(default=1, required=True)
    search_number = fields.Integer(default=1, required=True)
    negotiation_type = fields.Char(default='base_base')
    estimated_distance = fields.Float(help='Estimated distance to reach the user, in kilometers.', default=0.0)
    estimated_duration = fields.Float(help='Estimated duration to arrive to the user, in minutes.', default=0.0)
    estimated_cost = fields.Float(related='supplier_link_id.estimated_cost', store=True, readonly=False)
    real_distance = fields.Float(default=0.0)
    real_duration = fields.Float(default=0.0)
    cost_distance = fields.Float(default=0.0)
    bypass = fields.Boolean(default=False)
    user_amount_paid = fields.Float(related='supplier_link_id.user_amount_paid', readonly=False)
    user_payment_lines_count = fields.Integer(related='supplier_link_id.user_payment_lines_count')

    # Assignation supplier fields
    ranking = fields.Integer(string='Ranking', default=0, readonly=True)
    supplier_phone = fields.Char(related='supplier_id.phone', string='Phone')
    supplier_phone_1 = fields.Char(related='supplier_id.x_phone_p1', string='Phone 1')
    supplier_phone_2 = fields.Char(related='supplier_id.x_phone_p2', string='Phone 2')
    supplier_phone_3 = fields.Char(related='supplier_id.x_phone_p3', string='Phone 3')
    supplier_phone_4 = fields.Char(related='supplier_id.x_phone_p4', string='Phone 4')
    supplier_phone_5 = fields.Char(related='supplier_id.x_phone_p5', string='Phone 5')
    assigned = fields.Char(string='Operator')
    latitude = fields.Char(copy=False)
    longitude = fields.Char(copy=False)
    route = fields.Json(copy=False)
    osrm = fields.Boolean(default=False, copy=False)

    # === EVIDENCE FIELDS === #
    service_evidence_ids = fields.One2many('ike.event.evidence', 'event_supplier_id', string='Evidence')

    # === SERVICE FIELDS === #
    subservice_id = fields.Many2one('product.product', related='event_id.sub_service_id')
    event_supplier_summary_data = fields.Html(compute='_compute_event_supplier_summary_data')
    travel_tracking_url = fields.Char(compute='_compute_travel_tracking_url')

    # === EVALUATION FIELDS === #
    evaluation_id = fields.Many2one('ike.event.supplier.evaluation', 'Evaluation', tracking=True, copy=False)
    evaluation_reevaluation = fields.Boolean(related='evaluation_id.reevaluation')
    evaluation_2_id = fields.Many2one('ike.event.supplier.evaluation', 'Second Evaluation', tracking=True, copy=False)
    evaluation_observations = fields.Text('Observations', copy=False)
    evaluation_informer = fields.Char('Informer', copy=False)
    evaluated = fields.Boolean(default=False)
    evaluation_locked = fields.Boolean(compute='_compute_evaluation_locked')

    # === DETAILS FIELDS === #
    supplier_link_id = fields.Many2one('ike.event.supplier.link')
    supplier_product_ids = fields.One2many(related='supplier_link_id.supplier_product_ids', readonly=False)
    amount_concept_subtotal = fields.Float(related='supplier_link_id.amount_concept_subtotal', string='Subtotal')
    amount_concept_vat = fields.Float(related='supplier_link_id.amount_concept_vat', string='VAT')
    amount_concept_total = fields.Float(related='supplier_link_id.amount_concept_total', string='Total')
    cost_invalid = fields.Boolean(related='supplier_link_id.cost_invalid')

    base_amount_concept_subtotal = fields.Float(related='supplier_link_id.base_amount_concept_subtotal', string='Subtotal agreement')
    base_amount_concept_vat = fields.Float(related='supplier_link_id.base_amount_concept_vat', string='VAT agreement')
    base_amount_concept_total = fields.Float(related='supplier_link_id.base_amount_concept_total', string='Total agreement')

    # === ONCHANGE === #
    @api.onchange('truck_id')
    def _onchange_truck_id(self):
        if self.truck_id:
            self.assigned = self.truck_id.driver_id.name
            self.name = f"{_('License Plate')}: {self.truck_id.license_plate}"

    # === COMPUTES === #
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f'{rec.supplier_id.name}, {rec.name}'

    @api.depends('supplier_id')
    def _compute_truck_domain(self):
        for rec in self:
            sub_res_id = self.env[rec.event_id.sub_service_res_model].browse(rec.event_id.sub_service_res_id)
            service_vehicle_type_ids = []
            service_vehicle_type_ids = sub_res_id.service_vehicle_type_ids.ids  # type: ignore

            domain = [
                ('disabled', '=', False),
                ('x_vehicle_service_state', '=', 'available'),
                ('x_vehicle_type', 'in', service_vehicle_type_ids),
                ('x_partner_id', '=', rec.supplier_id.id),
                ('x_subservice_ids', 'in', [rec.event_id.sub_service_id.id]),
                ('driver_id', '!=', False),
            ]

            if rec.event_id.requires_federal_plates:
                domain.append(
                    ('x_federal_license_plates', '=', True),
                )

            rec.truck_domain = domain

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
            # FixMe: wrong validation
            states = (
                'searching',
                'assigned',
                'in_progress',
                'completed',
                'verifying',
                'closed',
                'cancel',
                'cancel_subsequently',
                'cancel_verifying',
                'cancel_closed',
            )
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
                location_fields = ['location_label', 'destination_label', 'destination_distance', 'destination_duration']
                location_record_fields = rec.event_id.fields_get(location_fields)
                location_record_data = rec.event_id.read(location_fields)[0]
                for field in location_fields:  # Location details
                    if field == 'destination_distance':  # Formatear distancia
                        location_record_data[field] = f"{round(location_record_data[field], 3)} km"
                    if field == 'destination_duration':
                        destination_duration_minutes, destination_duration_seconds =\
                            self.decimal_minutes_to_time(location_record_data[field])
                        location_record_fields[field] = {'string': _('Estimated Duration Destination')}

                        location_record_data[field] = (
                            _("%s minutes %s seconds") % (destination_duration_minutes, destination_duration_seconds))
                    event_summary_supplier_data += f"""
                        <div><span style='font-weight: bold;'>{location_record_fields[field]['string']}: </span>
                        <span>{location_record_data[field] or ''}</span></div>
                    """

                # Supplier section
                event_summary_supplier_data += "<h3 class='mt-3'>%s</h3>" % _('Assigned Supplier')

                supplier_fields = [
                    'supplier_id',
                    'assigned',
                    'estimated_distance',
                    'estimated_duration',
                    'assignation_type',
                    'truck_id',
                    'truck_plate'
                ]
                supplier_record_fields = rec.fields_get(supplier_fields)
                supplier_record_data = rec.read(supplier_fields)[0]

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
                    if field == 'estimated_distance':
                        supplier_record_data[field] = f"{round(supplier_record_data[field], 3)} km"
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

    def _compute_evaluation_locked(self):
        for rec in self:
            if rec.assignation_type not in ['manual', 'manual_manual']:
                rec.evaluation_locked = True
            else:
                previous = self.search([
                    ('event_id', '=', rec.event_id.id),
                    ('assignation_type', '=', 'manual'),
                    ('search_number', '=', rec.search_number),
                    ('sequence', '<', rec.sequence),
                ], order='sequence desc', limit=1)

                rec.evaluation_locked = not (not previous or previous.evaluation_id)

    # === DEFAULT === #
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        preparing_stage = self.env.ref("ike_event.ike_service_stage_preparing")
        res["stage_id"] = preparing_stage.id
        return res

    # === CRUD === #
    def write(self, vals):
        # truck_id changed
        previous_trucks = {}
        if 'truck_id' in vals:
            for rec in self:
                if rec.truck_id.id != vals['truck_id']:
                    vals['confirmed'] = False
                    previous_trucks[rec.id] = rec.truck_id

        # Evaluated
        if vals.get('evaluation_id'):
            vals['evaluated'] = True

        res = super().write(vals)

        # Binnacle
        if vals.get('evaluation_id') or vals.get('evaluation_2_id'):
            self._evaluation_binnacle(vals)

        # Release previous and set new distances.
        if 'truck_id' in vals:
            for rec in self:
                old_truck = previous_trucks.get(rec.id)
                new_truck = rec.truck_id
                if old_truck and old_truck != new_truck:
                    # Previous Vehicle State
                    rec._change_previous_vehicle_state(old_truck)
                    rec.assigned = new_truck.driver_id.name
                    rec.name = f"{_('License Plate')}: {new_truck.license_plate}"
                    # Set New Distance
                    rec._set_new_service_vehicle_distance()

        return res

    def _evaluation_binnacle(self, vals):
        # ToDo: Binnacle, Evaluation
        pass

    # === ACTION VIEW === #
    def action_view_evaluation(self):
        self.ensure_one()
        view_id = self.env.ref('ike_event.ike_event_supplier_evaluation_form_view').id
        return {
            'name': self.supplier_id.display_name + " " + _('Evaluation'),
            'view_mode': 'form',
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.supplier',
            'res_id': self.id,
            'views': [(view_id, 'form')],
            'context': {
                **self.env.context,
                'create': False,
                'edit': True,
                'from_add_concept': True,
                'from_internal': True,
            },
            'target': 'new',
        }

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
                'from_add_concept': True,  # self.selected is True or self.is_manual and self.state == 'available',
                'from_internal': True,
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
                'from_internal': True,
            },
            'target': 'new',
        }

    def action_view_ike_event_service_cost(self):
        list_view = self.env.ref('ike_event.ike_event_supplier_product_service_costs_list_view').id

        mapped = {}
        for rec in self:
            mapped[rec.supplier_link_id.id] = rec.id
        return {
            'name': _('Service costs'),
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.supplier.product',
            'view_mode': 'list',
            'views': [(list_view, 'list')],
            'search_view_id': False,
            'domain': [
                ('id', 'in', self.supplier_product_ids.ids),
                ('display_type', 'not in', ['line_section', 'line_note']),

            ],
            'target': 'new',
            'context': {
                **self.env.context,
                'mapped': json.dumps(mapped),
                'create': False,
                'edit': False,
            },
        }

    def action_view_ike_event_agreement_cost_final(self):
        list_view = self.env.ref('ike_event.ike_event_supplier_product_detail_base_cost_final_list_view').id

        is_assigned_user = self.event_id.assigned_user_id.id == self.env.user.id
        is_admin_user = self.env.user.has_group('base.group_system')
        can_edit = is_assigned_user or is_admin_user

        self.supplier_product_ids

        mapped = {}
        for rec in self:
            mapped[rec.supplier_link_id.id] = rec.id
        return {
            'name': _('Agreement costs'),
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.supplier.product',
            'view_mode': 'list',
            'views': [(list_view, 'list')],
            'search_view_id': False,
            'domain': [
                ('id', 'in', self.supplier_product_ids.ids),
                ('display_type', 'not in', ['line_section', 'line_note']),
            ],
            'target': 'new',
            'context': {
                **self.env.context,
                'mapped': json.dumps(mapped),
                'create': False,
                'edit': can_edit,
                'from_review_cost': not can_edit,
            },
        }

    def action_view_other_phones(self):
        self.ensure_one()
        view_id = self.env.ref('ike_event.ike_event_phone_wizard_view_form').id

        return {
            'name': _('Phone directory'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'ike.event.phone.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_ike_event_supplier_id': self.id,
            }
        }

    def action_open_change_vehicle(self):
        view_id = self.env.ref('ike_event.ike_event_supplier_vehicle_form_view').id
        return {
            'name': _('Change Vehicle'),
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.supplier',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                **self.env.context,
                'create': False,
                'edit': True,
            },
        }

    def action_open_travel_tracking(self):
        self.ensure_one()
        return {
            'name': _('Assigned Supplier: %s') % self.supplier_id.name,
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

    # === PUBLIC METHODS ===
    def get_selectable_vehicles(self):
        self.ensure_one()
        domain = expression.AND([list(self.truck_domain or []), [('x_vehicle_ref', '!=', False)]])
        domain = expression.OR([domain, [('id', '=', self.truck_id.id)]])
        vehicles = self.env['fleet.vehicle'].sudo().search(domain)
        return [
            {'id': vehicle.id, 'name': vehicle.name, 'license_plate': vehicle.license_plate}
            for vehicle in vehicles
        ]

    # === Auxiliary === #
    @staticmethod
    def decimal_minutes_to_time(decimal_minutes):
        minutes = int(decimal_minutes)
        seconds = round((decimal_minutes - minutes) * 60)
        return minutes, seconds


class IkeEventSupplierLink(models.Model):
    _name = 'ike.event.supplier.link'
    _description = 'Event Supplier Link'

    event_id = fields.Many2one('ike.event', ondelete='cascade', required=True)
    supplier_id = fields.Many2one('res.partner', required=True, index=True, domain="[('x_is_supplier', '=', True)]")
    supplier_number = fields.Integer(required=True, readonly=True, default=1)
    manual_notification = fields.Boolean(default=True)
    aux_truck_id = fields.Many2one('fleet.vehicle', 'Service Vehicle')
    aux_estimated_distance_km = fields.Float()
    aux_estimated_duration_m = fields.Float()
    aux_cost_distance_km = fields.Float()

    estimated_cost = fields.Float(default=0.0, compute='_compute_estimated_cost', store=True)

    # === AUTHORIZATION FIELDS === #
    type_authorization_id = fields.Many2one('custom.additional.concept.authorizer.type')
    reason_authorizer_id = fields.Many2one('custom.reason.authorizing.additional.costs')
    authorizer_id = fields.Many2one('res.partner', string="Responsible Name")
    authorization_by_nu = fields.Boolean(related='type_authorization_id.is_nu')
    authorizer_domain = fields.Binary(compute="_compute_authorizer_domain")
    nu_user_id = fields.Many2one(related='event_id.user_id')
    authorizer = fields.Char('Authorizer', compute="_compute_authorizer_name", store=True)
    user_amount_paid = fields.Float('Amount Paid to Supplier', default=0)
    user_payment_line_ids = fields.One2many(
        'ike.event.supplier.link.payment.line',
        'link_id',
        string='User Payment Lines',
    )
    user_payment_lines_count = fields.Integer(compute='_compute_user_payment_lines_count', store=True)

    # === LINE FIELDS === #
    supplier_product_ids = fields.One2many(
        'ike.event.supplier.product', 'event_supplier_link_id',
        domain=['|', ('base', '!=', True), ('parent_product_id', '!=', False)],
        string='Concepts')
    amount_concept_subtotal = fields.Float(string='Subtotal', compute='_compute_amount_supplier_product', store=True)
    amount_concept_vat = fields.Float(string='VAT', compute='_compute_amount_supplier_product', store=True)
    amount_concept_total = fields.Float(string='Total', compute='_compute_amount_supplier_product', store=True)
    cost_invalid = fields.Boolean(compute='_compute_amount_supplier_product', store=True)

    base_amount_concept_subtotal = fields.Float(
        string='Agreement Subtotal', compute='_compute_base_amount_supplier_product', store=True)
    base_amount_concept_vat = fields.Float(
        string='Agreement VAT', compute='_compute_base_amount_supplier_product', store=True)
    base_amount_concept_total = fields.Float(
        string='Agreement Total', compute='_compute_base_amount_supplier_product', store=True)

    # === EXCEEDS COVERAGE FIELDS === #
    exceeds_coverage = fields.Boolean(compute='_compute_exceeds_coverage')

    # === COMPUTE METHODS === #
    @api.depends('supplier_product_ids.subtotal', 'supplier_product_ids.vat')
    def _compute_amount_supplier_product(self):
        for rec in self:
            amount_subtotal = 0.0
            amount_total = 0.0
            amount_vat = 0.0
            cost_invalid = False

            # Filter negative nu payments.
            for line in rec.supplier_product_ids.filtered(lambda x: not x.display_type and x.cost_price >= 0):
                amount_subtotal += line.cost_price
                amount_vat += line.vat
                amount_total = amount_subtotal + amount_vat
                if not cost_invalid:
                    cost_invalid = line.cost_price == 0

            rec.amount_concept_subtotal = amount_subtotal
            rec.amount_concept_vat = amount_vat
            rec.amount_concept_total = amount_total

            rec.cost_invalid = cost_invalid

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

    @api.depends(
        'event_id.user_membership_id.membership_plan_id',
        'base_amount_concept_total'
    )
    def _compute_exceeds_coverage(self):
        user = self.env.user
        # ToDo: Change when you have the CCC coordinator user
        has_group = user.has_group('base.group_system')

        for rec in self:
            coverage_plan = rec.event_id.user_membership_id.membership_plan_id
            coverage_plan_line = coverage_plan.product_line_ids.filtered(
                lambda x: rec.event_id.service_id.id == x.service_id.id
                and rec.event_id.sub_service_id.id in x.sub_service_ids.ids
            )
            limit_amount_per_event = coverage_plan_line.limit_amount_per_event if coverage_plan_line else 0
            exceeds = rec.base_amount_concept_total > limit_amount_per_event

            rec.exceeds_coverage = exceeds and has_group

    @api.depends('user_payment_line_ids')
    def _compute_user_payment_lines_count(self):
        for rec in self:
            rec.user_payment_lines_count = len(rec.user_payment_line_ids.ids)

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

        if self.authorization_by_nu and not self.user_payment_line_ids:
            raise UserError(
                _("The authorization type requires a payment line.")
            )

        # ToDo: Send notification?

    def action_accept_authorization(self):
        self.ensure_one()
        event_id = self.event_id.sudo()

        if not self.type_authorization_id and not self.reason_authorizer_id:
            raise ValidationError(
                _("Authorization is not possible because there are incomplete authorization fields.")
            )

        if self.authorization_by_nu and not self.user_payment_line_ids:
            raise UserError(
                _("The authorization type requires a payment line.")
            )

        authorized_amount = max(event_id.previous_amount + event_id.current_amount, event_id.covered_amount)
        authorizer = (
            self.nu_user_id.display_name
            if self.authorization_by_nu
            else self.authorizer_id.display_name
        )
        event_id.authorized_amount = authorized_amount
        event_authorization_id = self.sudo().env['ike.event.authorization'].create({
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
        event_id.accept_authorization(event_authorization_id.id)

        if event_id.supplier_search_type in ['manual_manual', 'manual']:
            event_id.broadcastEventReload(1)

        # Start automatic notifications
        event_id.action_start_notifications()

    def action_reject_authorization(self):
        self.ensure_one()
        # ToDo: Reject?
        print("action_reject_authorization")

    # == SUPPLIER ADD ACTIONS === #
    def action_set_products(self):
        self.ensure_one()
        if self.aux_truck_id:
            supplier_center_id = self.aux_truck_id.x_center_id
            supplier_id = self.aux_truck_id.x_center_id.parent_id
            negotiation_type = supplier_id.x_negotiation_type

            center_distance_id = self.event_id._get_center_distances(supplier_center_id)

            distance_km: float = center_distance_id.center_origin_distance_km
            destination_distance = self.event_id.destination_distance or 0.0
            total_distance_km = 0.0

            if negotiation_type == 'base_base':
                total_distance_km = (total_distance_km + destination_distance) * 2.0
            elif negotiation_type == 'base_destination':
                total_distance_km = distance_km + destination_distance
            elif negotiation_type == 'origin_destination':
                total_distance_km = destination_distance
            elif negotiation_type == 'base_concept':
                total_distance_km = 0.0

            total_distance_km = int(-(-total_distance_km // 1))  # To integer

            # Add
            self.aux_cost_distance_km = total_distance_km
            self.aux_estimated_distance_km = center_distance_id.center_origin_duration_m
            self.aux_estimated_duration_m = center_distance_id.center_origin_duration_m
            products_data = self.event_id.get_supplier_products_data(
                supplier_center_id.id,
                self.aux_truck_id.x_center_id.parent_id.id,
                total_distance_km,
            )
            self.supplier_product_ids = products_data

    # Horizontally
    def add_products_horizontally(self, lines):
        for rec in self:
            current_product_ids = rec.supplier_product_ids.ids
            for line in lines:
                new_products_data = []
                if line['product_id'] not in current_product_ids:
                    new_products_data.append(Command.create({
                        'product_id': line['product_id'],
                        'quantity': line['quantity'],
                        'unit_price': line['unit_price'],
                        'authorization_pending': True,
                        'is_manual': True,
                        'supplier_number': rec.supplier_number,
                    }))
            rec.with_context(not_add_horizontally=True, from_internal=False).supplier_product_ids = new_products_data


class IkeEventSupplierLinkPaymentLine(models.Model):
    _name = 'ike.event.supplier.link.payment.line'
    _description = 'Event Supplier Payment Link Line'

    link_id = fields.Many2one('ike.event.supplier.link', 'Event Supplier', required=True, ondelete='cascade')
    event_id = fields.Many2one(related='link_id.event_id')
    supplier_id = fields.Many2one(related='link_id.supplier_id')
    supplier_number = fields.Integer(related='link_id.supplier_number')

    payment_type = fields.Selection([
        ('link', 'Payment Link'),
        ('cash', 'Cash')
    ], 'Payment Type', default='link', required=True)
    payment_datetime = fields.Datetime('Payment Datetime', required=True, default=fields.Datetime.now)
    amount = fields.Float('Amount', required=True)

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(
                    _("The payment amount must be greater than zero.")
                )

            link = line.link_id
            if link.authorization_by_nu and link.user_payment_line_ids:
                total_amount_payment = sum(link.user_payment_line_ids.mapped('amount'))
                if total_amount_payment > link.amount_concept_subtotal:
                    raise ValidationError(
                        _("The advance payment total exceeds the subtotal")
                    )


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
