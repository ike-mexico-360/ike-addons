# -*- coding: utf-8 -*-

import json
import logging
import requests

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.safe_eval import safe_eval
from .other_models.ike_event_batcher import event_batcher


_logger = logging.getLogger(__name__)


class IkeEvent(models.Model):
    _name = 'ike.event'
    _inherit = ['ike.event.base', 'mail.thread', 'mail.tracking.duration.mixin', 'mail.activity.mixin', 'mail.render.mixin']
    _description = 'Event'
    _track_duration_field = 'stage_id'
    _order = 'id desc'

    # Flow fields
    sections = fields.Json(compute='_compute_sections', store=True, copy=False)

    # nu fields
    nu_name = fields.Char('Nu user name')
    vip_user = fields.Boolean(related="user_id.vip_user", string='VIP User')
    user_membership_id = fields.Many2one('custom.membership.nus', 'Membership')
    user_phone = fields.Char(related='user_id.phone', string='Main Phone')
    membership_display_mask = fields.Char(related='user_membership_id.x_display_mask', string='Display Mask')
    key_identification = fields.Char(related='user_membership_id.key_identification', string='Key Identification')
    membership_validity = fields.Boolean(related='user_membership_id.subscription_validity', string='Membership Validity', store=False)
    preference_contact = fields.Selection(related='user_id.preference_contact', readonly=False, default='whatsapp')

    # user extra fields
    user_by = fields.Selection([
        ('by_id', 'User ID'),
        ('by_other', 'Other'),
    ], default='by_id')
    user_additional_name = fields.Char(string='User Additional Name')
    user_additional_last_name = fields.Char(string='User Additional Lastname')
    user_additional_phone = fields.Char(string='User Additional Phone')

    # Service fields
    service_id = fields.Many2one('product.category', index=True, tracking=True)
    service_domain = fields.Binary('Service Domain', compute='_compute_service_domain')
    service_ref = fields.Char(related='service_id.x_ref')
    service_res_model = fields.Char('Service Input Model', compute='_compute_service_res_model', store=True)
    service_res_id = fields.Many2oneReference('Service Input', model_field='service_res_model', copy=False)
    service_survey_input_id = fields.Many2one('survey.user_input', 'Service Survey Input', copy=False)
    service_input_ref = fields.Reference([
        ('ike.service.input.vial', 'Vial'),
    ], compute='_compute_service_input_ref', store=False)
    service_type_id = fields.Many2one(
        'ike.event.service.type',
        'Service type',
        default=lambda self: self.env.ref('ike_event.Service_emergence').id,
        ondelete='set null')

    # Sub-service fields
    sub_service_id = fields.Many2one(
        'product.product', 'Sub-Service',
        domain="[('categ_id', '=', service_id), ('x_input_res_model', '!=', False)]",
        index=True, copy=False, tracking=True)
    sub_service_ref = fields.Char(related='sub_service_id.default_code')
    sub_service_res_model = fields.Char('Sub-Service Input Model', compute='_compute_sub_service_res_model', store=True, copy=False)
    sub_service_res_id = fields.Many2oneReference(string='Sub-Service Input', model_field='sub_service_res_model', copy=False)
    sub_service_survey_input_id = fields.Many2one('survey.user_input', string='Sub-Service Survey Input', copy=False)

    # Service available fields
    services_allowed = fields.Integer(
        compute="_compute_selected_sub_service_counters",
        store=False
    )
    services_available = fields.Integer(
        compute="_compute_selected_sub_service_counters",
        store=False
    )
    selected_sub_service_name = fields.Char(
        string="selected_sub_service_name",
        compute="_compute_selected_sub_service_counters",
        store=False
    )
    count_json = fields.Char(
        string="Sub Service JSON",
        compute='_compute_sub_service_counter_json',
        store=False
    )

    # Locations fields
    location_label = fields.Char('Origin')
    location_latitude = fields.Char()
    location_longitude = fields.Char()
    location_zip_code = fields.Char(size=10)
    requires_federal_plates = fields.Boolean()
    destination_label = fields.Char('Destination')
    destination_latitude = fields.Char()
    destination_longitude = fields.Char()
    destination_distance = fields.Float(help='Estimated distance to reach the destination, in kilometers.')
    destination_duration = fields.Float(help='Estimated duration to reach the destination, in minutes.')
    destination_route = fields.Json()
    destination_route_change = fields.Boolean(default=True)
    destination_zip_code = fields.Char(size=10)

    active = fields.Boolean(default=True, copy=False)

    # Authorization
    event_cost = fields.Char(string='Cost', default='$0.00', copy=False)
    covered_amount = fields.Float(tracking=True, copy=False)
    authorized_amount = fields.Float(tracking=True, copy=False)

    # Event Summary
    event_summary_id = fields.Many2one('ike.event.summary', copy=False)
    event_summary_user_data = fields.Json(
        related='event_summary_id.user_data', prefetch=False, readonly=False, copy=False)
    event_summary_service_data = fields.Json(
        related='event_summary_id.service_data', prefetch=False, readonly=False, copy=False)
    event_summary_user_service_data = fields.Json(
        related='event_summary_id.user_service_data', prefetch=False, readonly=False, copy=False)
    event_summary_location_data = fields.Json(
        related='event_summary_id.location_data', prefetch=False, readonly=False, copy=False)
    event_summary_survey_data = fields.Json(
        related='event_summary_id.survey_data', prefetch=False, readonly=False, copy=False)
    event_summary_supplier_data = fields.Json(
        related='event_summary_id.supplier_data', prefetch=False, readonly=False, copy=False)
    event_summary_user_sub_service_data = fields.Json(
        related='event_summary_id.user_sub_service_data', prefetch=False, readonly=False, copy=False)
    event_summary_event_data = fields.Json(
        related='event_summary_id.event_data', prefetch=False, readonly=False, copy=False)

    # Conclusion
    cause_rate = fields.Boolean(default=True, index=True, readonly=True, copy=False)
    cancel_on_time = fields.Boolean(readonly=True, copy=False)
    cancel_user_id = fields.Many2one('res.users', readonly=True, copy=False)
    cancel_reason_id = fields.Many2one('ike.event.cancellation.reason', readonly=True, copy=False)

    # Details
    service_product_ids = fields.One2many('ike.event.product', 'event_id', string='Event Concepts', copy=False)
    service_supplier_ids = fields.One2many('ike.event.supplier', 'event_id', string='Event Suppliers', copy=False)
    service_supplier_link_ids = fields.One2many('ike.event.supplier.link', 'event_id', 'Event Supplier Links', copy=False)
    service_evidence_ids = fields.One2many('ike.event.evidence', 'event_id', string='Evidence', copy=False)
    selected_supplier_ids = fields.One2many(
        'ike.event.supplier', 'event_id',
        string='Selected Suppliers',
        domain=[('selected', '=', True)],
        readonly=True,
        copy=False)
    child_ids = fields.One2many('ike.event', 'parent_id', 'Children', copy=False)

    ia_suggestion_done = fields.Boolean(default=False, copy=False)
    ia_suggestion_product_ids = fields.Json(string="AI Suggested Concepts", copy=False, default=lambda self: [])

    ike_event_coordinator_id = fields.Many2one(
        'res.users',
        string='Assign',
        copy=False,
        domain=lambda self: [
            ('active', '=', True),
            ('groups_id', 'in', [
                self.env.ref('custom_master_catalog.custom_group_ccc_coordinator').id,
                self.env.ref('custom_master_catalog.custom_group_ccc_analyst').id,
                self.env.ref('custom_master_catalog.custom_group_ccc_boss').id,
            ])
        ]
    )
    satisfaction_survey_input_id = fields.Many2one('survey.user_input', readonly=True, copy=False, prefetch=False)
    satisfaction_survey_input_url = fields.Char(string='Satisfaction Survey URL', readonly=True, copy=False, prefetch=False)

    # === DEFAULT === #
    @api.model
    def default_get(self, fields_list):
        rec = super().default_get(fields_list)
        draft_stage = self.env.ref("ike_event.ike_event_stage_draft")
        service_vial = self.env.ref("custom_master_catalog.ike_product_category_vial")
        rec["service_id"] = service_vial.id
        rec["stage_id"] = draft_stage.id
        # First two event types and takes the second one
        event_type_ids = self.env['custom.type.event'].search([], order='id asc', limit=2)
        if event_type_ids:
            rec['event_type_id'] = event_type_ids[1].id if len(event_type_ids) == 2 else event_type_ids[0].id
        return rec

    # === CRUD === #
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company_id = vals.get('company_id', self.default_get(['company_id'])['company_id'])
            self_comp = self.with_company(company_id)
            if vals.get('name', _('New')) == _('New'):
                seq_date = None
                event_date = None
                if 'event_date' in vals:
                    event_date = fields.Datetime.to_datetime(vals['event_date'])
                seq_date = fields.Datetime.context_timestamp(self, event_date or fields.Datetime.now())
                vals['name'] = self_comp.env['ir.sequence'].next_by_code('ike.event', sequence_date=seq_date) or '/'

        return super().create(vals_list)

    def write(self, vals):
        return super(IkeEvent, self).write(vals)

    def read(self, fields=None, load='_classic_read'):
        """
        Override read to return decrypted values when necessary
        """
        result = super(IkeEvent, self).read(fields=fields, load=load)
        # Only decrypt if encrypted fields are specifically requested
        if not fields or any(f in fields for f in ['user_phone', 'key_identification']):
            encryption_util = self.env['custom.encryption.utility']
            for record in result:
                if 'user_phone' in record and record['user_phone']:
                    try:
                        record['user_phone'] = encryption_util.decrypt_aes256(record['user_phone'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting user_phone: {str(e)}")
                if 'key_identification' in record and record['key_identification']:
                    try:
                        record['key_identification'] = encryption_util.decrypt_aes256(record['key_identification'])
                    except Exception as e:
                        _logger.warning(f"Error decrypting key_identification: {str(e)}")
        return result

    # === ONCHANGE === #
    @api.onchange('user_id')
    def _onchange_user_id(self):
        self.user_membership_id = None

    @api.onchange('service_id')
    def _onchange_service_id(self):
        self.sub_service_id = None

    @api.onchange('location_latitude', 'location_longitude', 'destination_latitude', 'destination_longitude')
    def _onchange_location(self):
        self.destination_route_change = True

    # === COMPUTE === #
    def _compute_service_input_ref(self):
        for rec in self:
            if rec.service_res_model and rec.service_res_id:
                rec.service_input_ref = f"{rec.service_res_model},{rec.service_res_id}"
            else:
                rec.service_input_ref = False

    @api.depends('service_id')
    def _compute_service_domain(self):
        exclude_services = [
            self.env.ref('product.product_category_all').id,
            self.env.ref('product.product_category_1').id,
            self.env.ref('product.cat_expense').id
        ]
        self.service_domain = [
            ('disabled', '=', False),
            ('id', 'not in', exclude_services),
            ('x_input_res_model', '!=', False),
        ]

    @api.depends('service_id')
    def _compute_service_res_model(self):
        for rec in self:
            if rec.service_id and rec.service_id.x_input_res_model:
                rec.service_res_model = rec.service_id.x_input_res_model
            else:
                rec.service_res_model = None
            rec.service_res_id = None

    @api.depends('sub_service_id')
    def _compute_sub_service_res_model(self):
        for rec in self:
            if rec.sub_service_id and rec.sub_service_id.x_input_res_model:
                rec.sub_service_res_model = rec.sub_service_id.x_input_res_model
            else:
                rec.sub_service_res_model = None
            rec.sub_service_res_id = None

    @api.depends('stage_id', 'step_number')
    def _compute_sections(self):
        """
            result = {
                'user_data': True,
                'service_data': True,
            }
        """
        event_flow = self._get_event_flow_dict()
        for rec in self:
            stage_ref = rec.stage_ref
            step_number = rec.step_number

            stage_conf = event_flow.get(stage_ref, {})
            step_conf = stage_conf.get(str(step_number), {})

            sections = step_conf.get('sections', ['dummy'])
            summary = step_conf.get('summary', {'top': [], 'bottom': []})
            if 'service_specific' in step_conf:
                step_specific_conf = step_conf.get('service_specific', {})
                service_model = 'dummy'
                if rec.service_res_model in step_specific_conf:
                    service_model = rec.service_res_model
                elif rec.sub_service_res_model in step_specific_conf:
                    service_model = rec.sub_service_res_model

                sections = step_specific_conf.get(service_model, {}).get('sections', ['dummy'])
                summary = step_specific_conf.get(service_model, {}).get('summary', {'top': [], 'bottom': []})

            sections_data = {section: True for section in sections}
            sections_data['summary'] = summary
            rec.sections = sections_data

    @api.depends('user_id')
    def _compute_sub_service_counter_json(self):
        for rec in self:
            rec.count_json = rec._build_sub_service_counter_json()

    @api.depends('sub_service_id', 'count_json')
    def _compute_selected_sub_service_counters(self):
        for rec in self:
            rec.services_allowed = 0
            rec.services_available = 0
            rec.selected_sub_service_name = False

            if not rec.count_json:
                continue

            try:
                data = json.loads(rec.count_json)
            except Exception:
                continue

            selected = next(
                (
                    item for item in data
                    if item['sub_service_id'] == rec.sub_service_id.id
                ),
                None
            )

            if not selected:
                continue

            rec.services_allowed = selected.get('coverage_events', 0)
            rec.services_available = selected.get('available', 0)
            rec.selected_sub_service_name = selected.get('sub_service_ref')

    # === STAGE ACTIONS === #
    def action_completed(self):
        self.stage_id = self.env.ref('ike_event.ike_event_stage_completed').id
        self.action_create_satisfaction_survey()

    def action_verify(self):
        total_amount = sum(self.selected_supplier_ids.mapped('base_amount_concept_total'))
        if total_amount <= self.covered_amount:
            self.action_close()
        else:
            self.stage_id = self.env.ref('ike_event.ike_event_stage_verifying').id

    def action_close(self):
        self.stage_id = self.env.ref('ike_event.ike_event_stage_closed').id
        self.action_create_purchase_orders()

    def action_create_purchase_orders(self):
        pass

    def action_create_satisfaction_survey(self):
        for rec in self:
            service_satisfaction_survey_id = rec.service_id.sudo().x_satisfaction_survey_id
            if not rec.satisfaction_survey_input_id and service_satisfaction_survey_id:
                user_input_id = self.env['survey.user_input'].create({
                    'event_id': rec.id,
                    'survey_id': service_satisfaction_survey_id.id,
                })
                rec.satisfaction_survey_input_id = user_input_id.id
                rec.satisfaction_survey_input_url = (
                    f'/survey/{service_satisfaction_survey_id.access_token}/{user_input_id.access_token}'
                )

    def action_testing_reload(self):
        self.broadcastEventReload(4)

    # === FLOW ACTIONS === #
    def action_forward(self):
        event_flow = self._get_event_flow_dict()
        stage_keys = list(event_flow.keys())
        for rec in self:
            stage_ref = rec.stage_ref
            step_number = rec.step_number

            stage_conf = event_flow.get(stage_ref, {})
            step_conf = stage_conf.get(str(step_number))

            if step_conf:
                current_step = self._get_current_step(step_conf)

                if 'actions' in current_step:
                    for action_name in current_step['actions']:
                        action_function = getattr(self, action_name)
                        action_function()

            # ? SPECIAL TREATMENT
            if (stage_ref == 'assigned' or stage_ref == 'in_progress') and step_number == 3:
                next_stage_ref = rec.stage_ref
                step_number = 1
            else:
                next_stage_ref, step_number = self._find_next_step(event_flow, stage_keys, stage_conf, stage_ref, step_number)
            if next_stage_ref != stage_ref:
                next_stage_id = self.env.ref("ike_event.ike_event_stage_" + next_stage_ref)
                rec.stage_id = next_stage_id
                # Broadcast stage changed
                event_batcher.add_event_notification(
                    self.env.cr.dbname,
                    'IKE_CHANNEL_LIST',
                    'IKE_CHANNEL_LIST_LISTEN', {
                        'id': rec.id,
                        'stage_ref': rec.stage_ref,
                    }, batch_timeout=10)
            rec.step_number = step_number

    def action_backward(self):
        event_flow = self._get_event_flow_dict()
        stage_keys = list(event_flow.keys())
        for rec in self:
            stage_ref = rec.stage_ref
            step_number = rec.step_number

            stage_conf = event_flow.get(stage_ref, {})
            step_conf = stage_conf.get(str(step_number))

            previous_stage_ref, step_number = self._find_previous_step(
                event_flow, stage_keys, stage_conf, step_conf, stage_ref, step_number)
            if previous_stage_ref != stage_ref:
                previous_stage_id = self.env.ref("ike_event.ike_event_stage_" + previous_stage_ref)
                rec.stage_id = previous_stage_id
                # Broadcast stage changed
                event_batcher.add_event_notification(
                    self.env.cr.dbname,
                    'IKE_CHANNEL_LIST',
                    'IKE_CHANNEL_LIST_LISTEN', {
                        'id': rec.id,
                        'stage_ref': rec.stage_ref,
                    }, batch_timeout=10)
            rec.step_number = step_number

    def _find_next_step(self, event_flow, stage_keys, stage_conf, stage_ref, step_number):
        stage_index = stage_keys.index(stage_ref)
        step_keys = list(stage_conf.keys())
        step_index = step_keys.index(str(step_number))
        for i in range(step_index + 1, len(step_keys)):
            next_step = step_keys[i]
            step_conf = stage_conf.get(str(next_step))
            if self._check_domain(step_conf) and self._check_service_specific(step_conf):
                return stage_ref, int(next_step)

        for i in range(stage_index + 1, len(stage_keys)):
            next_stage = stage_keys[i]
            stage_conf = event_flow.get(next_stage, {})
            step_keys = list(stage_conf.keys())

            for step in step_keys:
                step_conf = stage_conf.get(step)

                if self._check_domain(step_conf) and self._check_service_specific(step_conf):
                    return next_stage, int(step)

        return stage_ref, step_number

    def _find_previous_step(self, event_flow, stage_keys, stage_conf, step_conf, stage_ref, step_number):
        stage_index = stage_keys.index(stage_ref)
        step_keys = list(stage_conf.keys())
        if str(step_number) in step_keys:
            step_index = step_keys.index(str(step_number))
        else:
            step_index = 0
        for i in range(step_index - 1, -1, -1):
            next_step = step_keys[i]
            step_conf = stage_conf.get(str(next_step))
            if self._check_domain(step_conf) and self._check_service_specific(step_conf):
                return stage_ref, int(next_step)

        for i in range(stage_index - 1, -1, -1):
            next_stage = stage_keys[i]
            stage_conf = event_flow.get(next_stage, {})
            step_keys = list(stage_conf.keys())

            for i in range(len(step_keys) - 1, -1, -1):
                step = step_keys[i]
                step_conf = stage_conf.get(step)

                if self._check_domain(step_conf) and self._check_service_specific(step_conf):
                    return next_stage, int(step)

        return stage_ref, step_number

    def _check_domain(self, step_conf):
        if 'domain' not in step_conf:
            return True

        domain = step_conf['domain']
        return len(self.filtered_domain(domain))

    def _check_service_specific(self, step_conf):
        if 'service_specific' not in step_conf:
            return True

        service_specific = step_conf['service_specific']
        if self.service_res_model in service_specific:
            return True
        elif self.sub_service_res_model in service_specific:
            return True
        else:
            return False

    def _get_current_step(self, step_conf):
        if 'service_specific' not in step_conf:
            return step_conf

        service_specific = step_conf['service_specific']
        if self.service_res_model in service_specific:
            return service_specific[self.service_res_model]
        elif self.sub_service_res_model in service_specific:
            return service_specific[self.sub_service_res_model]
        else:
            return {'sections': [], 'actions': []}

    def _get_event_flow_dict(self):
        event_flow_ids = self.env['ike.event.flow'].sudo().search(domain=[('active', '=', True)], order='sequence')
        result = {}

        for event_flow_id in event_flow_ids:
            if not result.get(event_flow_id.stage_id.ref):
                result[event_flow_id.stage_id.ref] = {}

            stage = result[event_flow_id.stage_id.ref]
            stage[str(event_flow_id.step_number)] = {}

            # Config
            not_specific = event_flow_id.detail_ids.filtered(lambda x: not x.service_specific)
            specific = event_flow_id.detail_ids.filtered(lambda x: x.service_specific)

            # Not Specific
            if len(not_specific):
                stage[str(event_flow_id.step_number)] = {
                    'sections': [x.name for x in not_specific if x.detail_type == 'section'],
                    'actions': [x.name for x in not_specific if x.detail_type == 'action'],
                    'summary': {
                        'top': [x.name for x in not_specific if x.detail_type == 'summary_top'],
                        'bottom': [x.name for x in not_specific if x.detail_type == 'summary_bottom'],
                    },
                }

            # Specific
            if len(specific):
                services = specific.mapped('service_specific')
                services = [x.strip() for item in services for x in str(item).split(",")]
                services = list(set(services))
                stage[str(event_flow_id.step_number)]['service_specific'] = {}
                for service in services:
                    stage[str(event_flow_id.step_number)]['service_specific'][service] = {
                        'sections': [
                            x.name for x in specific if x.detail_type == 'section' and x.service_specific == service],
                        'actions': [
                            x.name for x in specific if x.detail_type == 'action' and x.service_specific == service],
                        'summary': {
                            'top': [
                                x.name for x in specific if x.detail_type == 'summary_top' and x.service_specific == service],
                            'bottom': [
                                x.name for x in specific if x.detail_type == 'summary_bottom' and x.service_specific == service],
                        },
                    }

            # Domain
            if event_flow_id.condition_domain:
                stage[str(event_flow_id.step_number)]['domain'] = safe_eval(event_flow_id.condition_domain)

        return result

    # === ACTIONS SET DATA === #
    def action_set_user_data(self):
        for rec in self:
            rec.count_json = rec._build_sub_service_counter_json()
            if not rec.event_summary_id:
                event_summary_id = self.env['ike.event.summary'].create({
                    'event_id': rec.id,
                })
                rec.event_summary_id = event_summary_id.id
            rec.event_summary_id.set_user_data()

    def action_set_service_data(self):
        for rec in self:
            rec._set_service_res_id()
            rec._set_sub_service_res_id()
            rec.event_summary_id.set_service_data()

    def action_set_user_service_data(self):
        for rec in self:
            res_id = self.env[rec.service_res_model].search([('event_id', '=', rec.id)], limit=1)
            res_id.set_event_summary_user_service_data()  # type: ignore
            rec.event_summary_id.set_user_service_data()

            # Covered Amount
            covered_amount = 0.0
            membership_service_line_id = rec.user_membership_id.membership_plan_id.product_line_ids.filtered(
                lambda x: rec.sub_service_id in x.sub_service_ids)
            if membership_service_line_id:
                membership_service_line_id = membership_service_line_id[0]
                if membership_service_line_id.limit_ids:
                    # By Limit
                    covered_amount = membership_service_line_id.limit_ids[0].amount
                else:
                    # By Global
                    covered_amount = membership_service_line_id.limit_amount_per_event or 0.0
            rec.sudo().write({
                'covered_amount': covered_amount,
                'authorized_amount': covered_amount,
            })

    def action_set_location_data(self):
        self.event_summary_id.set_location_data()

    def action_set_survey_data(self):
        for rec in self:
            rec.event_summary_id.survey_data = {'title': f"<h4 class='text-ike-primary'>{_('Details')}</h4>", 'fields': []}
            rec.service_survey_input_id.set_event_summary_survey_data()
            rec.sub_service_survey_input_id.set_event_summary_survey_data()
            rec.event_summary_id.set_survey_data()

    def action_set_destination_data(self):
        self._set_destination_route()
        self.event_summary_id.set_destination_data()

    def action_set_route_data(self):
        self._set_destination_route(True)

    def action_set_user_sub_service_data(self):
        for rec in self:
            res_id = self.env[rec.sub_service_res_model].search([('event_id', '=', rec.id)], limit=1, order='id desc')
            res_id.set_event_summary_user_subservice_data()  # type: ignore
            rec.event_summary_id.set_user_sub_service_data()

    def action_set_products_covered(self):
        """Algorithm to create service_product_ids"""

        for rec in self:
            concept_ids = rec.service_product_ids.filtered(lambda x: x.supplier_number == rec.supplier_number)

            section_covered = concept_ids.filtered(
                lambda p: p.display_type == 'line_section' and p.name == _('Concepts in coverage')
            )
            section_not_covered = concept_ids.filtered(
                lambda p: p.display_type == 'line_section' and p.name == _('Concepts out of coverage')
            )

            if not section_covered:
                section_covered = self.env['ike.event.product'].create({
                    'event_id': rec.id,
                    'name': _('Concepts in coverage'),
                    'display_type': 'line_section',
                    'supplier_number': rec.supplier_number,
                    'covered': True,
                    'mandatory': True,
                    'sequence': 1,
                })
            else:
                section_covered.write({'sequence': 1, 'covered': True, 'mandatory': True})

            if not section_not_covered:
                section_not_covered = self.env['ike.event.product'].create({
                    'event_id': rec.id,
                    'name': _('Concepts out of coverage'),
                    'display_type': 'line_section',
                    'supplier_number': rec.supplier_number,
                    'covered': True,
                    'mandatory': True,
                    'sequence': 1001,
                })
            else:
                section_not_covered.write({'sequence': 1001, 'covered': True, 'mandatory': True})

            membership_plan = rec.user_membership_id.membership_plan_id

            # ToDo: Implement algorithm or IA for products in coverage
            # Plan Concepts
            plan_product_ids = set(
                membership_plan.product_line_ids.filtered(
                    lambda x: x.service_id == rec.service_id and rec.sub_service_id in x.sub_service_ids
                ).mapped('detail_ids.product_id.id')
            )
            # Subservice Concepts
            concept_line_ids = rec.sub_service_id.concept_line_ids.filtered(
                lambda x: x.event_type_id == rec.event_type_id
            )
            base_concept_ids = concept_line_ids.mapped('base_concept_id').ids
            subservice_product_ids = set(base_concept_ids)

            # Suggestion Concepts IA
            ia_product_ids = set(rec.ia_suggestion_product_ids or [])

            current_products = concept_ids.filtered(lambda p: not p.display_type)
            current_product_ids = set(current_products.mapped('product_id.id'))

            # 1. Add subservice concepts (always required)
            products_to_add = subservice_product_ids - current_product_ids
            if rec.supplier_number == 1:
                for product_id in products_to_add:
                    product = self.env['product.product'].browse(product_id)
                    self.env['ike.event.product'].create({
                        'event_id': rec.id,
                        'product_id': product_id,
                        'uom_id': product.uom_id.id,
                        'mandatory': True,  # Subservice always required
                        'additional': False,
                        'base': True,
                        'covered': True,
                        'supplier_number': rec.supplier_number,
                    })

            # 2. Adding IA concepts compared to a coverage plan
            products_ia_to_add = ia_product_ids - current_product_ids - subservice_product_ids
            if rec.supplier_number == 1:
                for product_id in products_ia_to_add:
                    product = self.env['product.product'].browse(product_id)
                    self.env['ike.event.product'].create({
                        'event_id': rec.id,
                        'product_id': product_id,
                        'uom_id': product.uom_id.id,
                        'additional': False,
                        'base': False,
                        'mandatory': False,
                        'covered': product_id in plan_product_ids,  # True if it's on the coverage plan
                        'supplier_number': rec.supplier_number,
                    })

            # 3. Update all products: covered=True if in the plan or subservice, False if not
            for event_product in current_products:
                is_subservice = event_product.product_id.id in subservice_product_ids
                is_covered = is_subservice or event_product.product_id.id in plan_product_ids

                if event_product.covered != is_covered:
                    event_product.write({'covered': is_covered, 'additional': event_product.additional})

                if event_product.mandatory != is_subservice:
                    event_product.write({'mandatory': is_subservice, 'additional': event_product.additional})

                if event_product.base != is_subservice:
                    event_product.write({'base': is_subservice, 'additional': event_product.additional})

            concept_ids = rec.service_product_ids.filtered(
                lambda x: x.supplier_number == rec.supplier_number
            )

            covered_products = concept_ids.filtered(
                lambda p: p.covered and not p.display_type).sorted('id')

            seq = 2
            for prod in covered_products:
                prod.write({'sequence': seq})
                seq += 1

            not_covered_products = concept_ids.filtered(
                lambda p: not p.covered and not p.display_type).sorted('id')

            seq = 1002
            for prod in not_covered_products:
                prod.write({'sequence': seq})
                seq += 1

    def action_set_product_data(self):
        pass

    def action_set_supplier_data(self):
        # stage_assigned = self.env.ref('ike_event.ike_service_stage_assigned').id
        for rec in self:
            if not rec.selected_supplier_ids:
                raise UserError(_('You must have a supplier selected.'))
            rec.event_summary_id.set_supplier_data()
            preparing_stage_id = self.env.ref('ike_event.ike_service_stage_preparing')
            service_supplier_id = rec.service_supplier_ids.filtered_domain([
                ('state', '=', 'accepted'),
                ('selected', '=', True),
                ('stage_id', '=', preparing_stage_id.id)
            ])
            if service_supplier_id:
                # service_supplier_id.stage_id = stage_assigned
                service_supplier_id.action_assign()

    def action_set_event_data(self):
        self.event_summary_id.set_event_data()

    # === EXTRA METHODS === #
    def _set_service_res_id(self):
        for rec in self:
            if not rec.service_res_model:
                continue
            # Dynamic Model
            res_id = self.env[rec.service_res_model].search([('event_id', '=', rec.id)], limit=1)
            if not res_id:
                res_id = self.env[rec.service_res_model].create({
                    'event_id': rec.id,
                    'name': rec.name + ' - ' + _('Service Input'),
                })
            rec.service_res_id = res_id.id
            # Survey User Input
            if rec.service_id.x_survey_id:
                survey_input_id = self.env['survey.user_input'].search([
                    ('event_id', '=', rec.id),
                    ('survey_id', '=', rec.service_id.x_survey_id.id),
                ], limit=1)
                if not survey_input_id:
                    survey_input_id = self.env['survey.user_input'].create({
                        'event_id': rec.id,
                        # 'name': rec.name + ' - ' + _('Service Survey Input'),
                        'partner_id': self.env.user.partner_id.id,
                        'survey_id': rec.service_id.x_survey_id.id,
                    })
                rec.service_survey_input_id = survey_input_id.id

    def _set_sub_service_res_id(self):
        for rec in self:
            if not rec.sub_service_res_model:
                continue
            # Dynamic Model
            res_id = self.env[rec.sub_service_res_model].search([('event_id', '=', rec.id)], limit=1)
            if not res_id:
                new_sub_service_data = {
                    'event_id': rec.id,
                    'name': rec.name + ' - ' + _('Sub-Service Input'),
                }
                # ToDo: Default truck type id
                # if rec.sub_service_res_model in ['tire_change', 'fuel_supply', 'other_fluid', 'battery_jump']:
                #     new_sub_service_data['truck_type_id'] = self.env.ref('')
                res_id = self.env[rec.sub_service_res_model].create(new_sub_service_data)
            rec.sub_service_res_id = res_id.id
            # Survey User Input
            if rec.sub_service_id.x_survey_id:
                survey_input_id = self.env['survey.user_input'].search([
                    ('event_id', '=', rec.id),
                    ('survey_id', '=', rec.sub_service_id.x_survey_id.id),
                ], limit=1)
                if not survey_input_id:
                    survey_input_id = self.env['survey.user_input'].create({
                        'event_id': rec.id,
                        # 'name': rec.name + ' - ' + _('Sub-Service Survey Input'),
                        'partner_id': self.env.user.partner_id.id,
                        'survey_id': rec.sub_service_id.x_survey_id.id,
                    })
                rec.sub_service_survey_input_id = survey_input_id.id

    def _set_destination_route(self, force=False):
        for rec in self:
            if not force and not rec.destination_route_change:
                continue
            if (
                not rec.location_latitude
                or not rec.location_longitude
                or not rec.destination_latitude
                or not rec.destination_longitude
            ):
                continue

            destination_distance_m, destination_duration_s, destination_route = (
                rec.get_destination_route(
                    rec.location_latitude, rec.location_longitude,
                    rec.destination_latitude, rec.destination_longitude,
                )
            )
            if destination_route:
                rec.destination_distance = (destination_distance_m or rec.destination_distance) / 1000
                rec.destination_duration = (destination_duration_s or rec.destination_duration) / 60
                rec.destination_route = destination_route

    def _build_sub_service_counter_json(self):
        self.ensure_one()
        result = []

        if not self.user_membership_id or not self.service_id:
            return json.dumps(result)

        details = self.user_membership_id.event_count_detail_ids.filtered(
            lambda d: d.service_id == self.service_id
        )

        for detail in details:
            available = max(
                detail.coverage_events - detail.events_of_period, 0
            )

            for sub_service in detail.sub_service_ids:
                result.append({
                    'service_id': detail.service_id.id,
                    'sub_service_id': sub_service.id,
                    'sub_service_ref': sub_service.name,
                    'coverage_events': detail.coverage_events,
                    'events_of_period': detail.events_of_period,
                    'available': available,
                })

        return json.dumps(result)

    @api.model
    def retrieve_event_data(self):
        """ This function returns the values to populate the custom dashboard in
            the event view.
        """
        self.browse().check_access('read')
        result = {
            'all_active_events': 0,
            'all_draft_events': 0,
            'my_active_events': 0,
            'my_draft_events': 0,
        }
        IKE_EVENT = self.env['ike.event']
        active_domain = [('stage_id.ref', 'in', ['capturing', 'searching', 'assigned', 'in_progress', 'completed', 'close'])]
        inactive_domain = [('stage_id.ref', 'in', ['draft'])]
        my_events_domain = [('write_uid', '=', self.env.uid)]
        result.update({
            'all_active_events': IKE_EVENT.search_count(active_domain),
            'all_draft_events': IKE_EVENT.search_count(inactive_domain),
            'my_active_events': IKE_EVENT.search_count(active_domain + my_events_domain),
            'my_draft_events': IKE_EVENT.search_count(inactive_domain + my_events_domain),
        })
        return result

    # === VIEW ACTIONS === #
    def action_view_subscription_details(self):
        pass
        # self.ensure_one()

        # view_id = self.env.ref('ike_event.custom_membership_nus_view_kanban').id

        # return {
        #     'name': _('Subscriptions'),
        #     'view_mode': 'kanban',
        #     'type': 'ir.actions.act_window',
        #     'res_model': 'custom.membership.nus',
        #     'views': [(view_id, 'kanban')],
        #     'domain': [('nus_id', '=', self.user_id.id)],
        #     'context': {
        #         'create': False,
        #     },
        #     'target': 'new',
        # }

    def action_show_history_wizard(self):
        self.ensure_one()
        view = self.env.ref('ike_event.ike_event_history_view_list')
        search_view = self.env.ref('ike_event.ike_event_history_view_search')
        completed_stage = self.env.ref('ike_event.ike_event_stage_completed')
        return {
            'name': _('Service history'),
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event',
            'view_mode': 'list',
            'views': [(view.id, 'list')],
            'search_view_id': search_view.id,
            'target': 'new',
            'domain': [
                ('id', '!=', self.id),
                ('user_id', '=', self.user_id.id),
                ('sub_service_id', '=', self.sub_service_id.id),
                ('stage_id', '=', completed_stage.id),
            ],
        }

    def action_view_event_history_detail(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_url",
            "url": f"/odoo/ike-event-screen/{self.id}",
            "target": "new"
        }

    # === ACTION CANCEL === #
    def open_cancel_wizard(self):
        self.ensure_one()
        view_id = self.env.ref('ike_event.ike_event_confirm_wizard_view_form').id
        return {
            'name': _('Cancel'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'ike.event.confirm.wizard',
            'view_id': view_id,
            'views': [(view_id, 'form')],
            'target': 'new',
            'context': {
                'default_res_model': 'ike.event',
                'default_res_ids': str(self.mapped('id')),
                'default_action_name': 'action_cancel',
                'ike_event_cancel': True,
                'is_cancel': True,
            }
        }

    def action_cancel(self, cancel_reason_id: int, reason_text=None):
        self.ensure_one()
        # ToDo: cancellation requirements?
        # Supplier(s)
        for service_supplier_id in self.selected_supplier_ids:
            service_supplier_id.action_event_cancel(cancel_reason_id, reason_text)

        not_cancelled = self.selected_supplier_ids.filtered(lambda x: x.state not in ['cancel', 'cancel_supplier', 'cancel_event'])
        if not_cancelled:
            raise ValidationError(_('It could not be cancelled'))

        # Event
        self._action_cancel(cancel_reason_id, reason_text)

    def _action_cancel(self, cancel_reason_id: int, reason_text=None):
        self.ensure_one()
        if self.stage_ref in ['draft', 'capturing', 'searching']:
            stage_id = self.env.ref('ike_event.ike_event_stage_cancelled')
        else:
            stage_id = self.env.ref('ike_event.ike_event_stage_cancelled_subsequently')
        self.stage_id = stage_id.id
        self.cancel_reason_id = cancel_reason_id
        self.cancel_user_id = self.env.user.id

    # === ACTION DUPLICATE === #
    def action_duplicate(self):
        self.ensure_one()
        new_event_id = self.copy()
        new_event_id.parent_id = self.id
        # Service Model
        if self.service_res_model and self.service_res_id:
            service_res_id = self.env[self.service_res_model].browse(self.service_res_id)
            new_service_res_id = service_res_id.copy()
            new_service_res_id.name = new_event_id.name + ' - ' + _('Service Input')  # type: ignore
            new_service_res_id.event_id = new_event_id.id  # type: ignore
        new_event_id._set_service_res_id()

    def action_open_duplicate_wizard(self):
        self.ensure_one()

        return {
            'name': _('Duplicate event'),
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event.duplicate.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_event_id': self.id
            }
        }

    # === PUBLIC METHODS === #
    @api.model
    def get_ike_event_popup_action(self, type):
        """ Returns the action to be used in the popup menu """
        name = _('Events')
        domain = []
        if type == 'active':
            name = _('Active Events')
            domain = [('stage_id.ref', 'in', ['capturing', 'searching', 'assigned', 'in_progress'])]
        elif type == 'inactive':
            name = _('Draft Events')
            domain = [('stage_id.ref', 'in', ['draft'])]
        action = {
            'name': name,
            'res_model': 'ike.event',
            'type': 'ir.actions.act_window',
            'view_mode': 'list',
            'views': [(self.env.ref('ike_event.view_ike_event_list_secondary').id, 'list')],
            'domain': domain,
            'context': {
                'create': False,
            },
            'target': 'new',
        }
        return action

    def get_user_phone(self):
        encryption_util = self.env['custom.encryption.utility']
        if self.user_additional_phone:
            try:
                return encryption_util.decrypt_aes256(self.user_additional_phone)
            except Exception as e:
                _logger.warning(f"Error decrypting complete_phone: {str(e)}")

    def get_destination_route(
        self,
        location_latitude,
        location_longitude,
        destination_latitude,
        destination_longitude,
        polyline=True,
    ):
        self.ensure_one()
        if not location_latitude or not location_longitude:
            raise ValidationError(_('No latitude or longitude was assigned.'))

        api_key = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')
        if not api_key:
            raise UserError(_(
                "API key for GeoCoding (Routes) required.\n"
            ))
        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        field_mask = [
            "routes.duration,routes.distanceMeters",
            # "routes.legs.steps.distanceMeters",
        ]
        if polyline:
            field_mask.append("routes.legs.steps.polyline.encodedPolyline")
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": ",".join(field_mask),
        }

        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": location_latitude,
                        "longitude": location_longitude,
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destination_latitude,
                        "longitude": destination_longitude,
                    }
                }
            },
            "travelMode": "DRIVE",
        }

        destination_distance_m = 0.0
        destination_duration_s = 0.0
        destination_route = None
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            result = response.json()
            if len(result['routes']):
                route = result['routes'][0]
                destination_distance_m = float(route['distanceMeters'])
                destination_duration_s = float(str(route['duration']).replace('s', ''))
                if route.get('legs') and len(route['legs']) and route['legs'][0].get('steps'):
                    destination_route = route['legs'][0].get('steps')
        except Exception as e:
            _logger.error(f"Error geolocation routes server: {str(e)}")

        return destination_distance_m, destination_duration_s, destination_route


class IkeEventStage(models.Model):
    _name = 'ike.event.stage'
    _description = 'Event Stage'
    _order = 'sequence, id'

    name = fields.Char(translate=True)
    ref = fields.Char()
    sequence = fields.Integer(default=1)
    color = fields.Char()
    fold = fields.Boolean(default=False)
    hide_timer = fields.Boolean(default=False)
    last_stage = fields.Boolean(default=False)
    active = fields.Boolean(default=True)
