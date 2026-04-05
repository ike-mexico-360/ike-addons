# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup


class CustomMembershipPlan(models.Model):
    _name = 'custom.membership.plan'
    _description = 'Custom Membership Plan'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    commercial_name = fields.Char(string='Commercial Name')
    x_validation_pattern = fields.Char(string='Validation pattern', related="account_id.x_validation_pattern")
    x_display_mask = fields.Char(string='Display mask', related="account_id.x_display_mask")
    x_validation_pattern_second = fields.Char(string='Validation pattern', related="account_id.x_validation_pattern_second")
    x_display_mask_second = fields.Char(string='Display mask', related="account_id.x_display_mask_second")

    account_type_id = fields.Many2one(
        related='account_id.x_account_type_id',
        string='Account Type',
        tracking=True)

    account_identification_id = fields.Many2one(
        related='account_id.x_account_identification_id',
        string='Account Identification',
        tracking=True)
    second_account_identification_id = fields.Many2one(
        related='account_id.x_second_key_identification_id',
        string='Second Account Identification',
        tracking=True)
    check_second_key = fields.Boolean(
        related='account_id.x_check_second_key',
        string='Check second key')
    vat_rfc = fields.Char(
        string='RFC',
        related="account_id.x_parent_vat",
        tracking=True)

    contract_start_date = fields.Date(string='Start Date', tracking=True)
    contract_end_date = fields.Date(string='End Date', tracking=True)
    cicle_reset = fields.Selection(selection=[
        ('at the end of the year', 'At the end of the year'),
        ('aniversary date', 'Anniversary date')
    ])

    account_id = fields.Many2one(
        comodel_name='res.partner',
        string='Account',
        domain=[
            ('company_type', '=', 'company'), ('is_company', '=', True),
            ('x_is_account', '=', True), ('x_is_account', '=', True),
            ('disabled', '=', False)],
        tracking=True)

    product_line_ids = fields.One2many(
        'custom.membership.plan.product.line', 'membership_plan_id',
        string='Products Lines', tracking=True)

    active = fields.Boolean(string='Active', default=True)
    disabled = fields.Boolean(string='Disabled', default=False, tracking=True)

    # BrightPattern
    bp_account_ref = fields.Char(
        string='BP Reference',
        help=(
            "BrightPattern service reference value; this value will be "
            "used to search for the coverage plan when the call is "
            "received at the BrightPattern endpoint."
        ),
    )

    _sql_constraints = [(
        'membership_plan_uniq',
        "unique(name)",
        "Membership plan must be unique."
    )]

    # === ACTIONS === #
    def action_disable(self, reason=None):
        for rec in self:
            if reason:
                body = Markup("""
                    <ul class="mb-0 ps-4">
                        <li>
                            <b>{}: </b><span class="">{}</span>
                        </li>
                    </ul>
                """).format(
                    _('Disabled'),
                    reason,
                )
                rec.message_post(
                    body=body,
                    message_type='notification',
                    body_is_html=True)
        return super().action_disable(reason)


class CustomMembershipPlanProductLine(models.Model):
    _name = 'custom.membership.plan.product.line'
    _description = 'Membership plan Product Line'
    _rec_name = 'name'
    _parent_name = 'membership_plan_id'

    def _get_default_currency_id(self):
        return self.env.company.currency_id.id

    commercial_name = fields.Char(string='Commercial Name')
    name = fields.Char(string='Descripción', compute='_compute_name', store=True)
    membership_plan_id = fields.Many2one(
        "custom.membership.plan", string='Membership plan', ondelete='cascade')
    local = fields.Boolean(sub_tracking=True)
    national = fields.Boolean(sub_tracking=True)
    foreigner = fields.Boolean(sub_tracking=True)
    service_id = fields.Many2one('product.category', string='Service', sub_tracking=True)
    sub_service_ids = fields.Many2many('product.product', string='Subservice')
    limit_amount_per_event = fields.Integer(default=0)
    period_per_event = fields.Integer(default=0)
    period = fields.Selection([
        ('monthly', 'Monthly'),
        ('biannually', 'Biannually'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ], string='Period event', default='monthly', )
    limit_distance = fields.Float(string='Limit distance (km)')

    x_service_domain = fields.Binary(string="Service domain", compute="_compute_x_service_domain")
    x_product_domain = fields.Binary(string="Product domain", compute="_compute_x_product_domain")
    detail_ids = fields.One2many(
        'custom.membership.plan.line.product',
        'line_id',
        string='Conceptos'
    )
    limit_ids = fields.One2many(
        'custom.membership.plan.line.limit',
        'line_id',
        string='Limits'
    )
    currency_id = fields.Many2one("res.currency", string="Currency", default=_get_default_currency_id)
    considerations_html = fields.Html()
    exclusions_html = fields.Html()

    product_description_po = fields.Char(string='Description PO')
    sap_id_income = fields.Char()
    sap_id_outgoing = fields.Char()
    vehicle_weight_category_id = fields.Many2one(
        'custom.vehicle.weight.category',
        'Weight Category',
        domain="[('disabled', '=', False)]")

    @api.onchange('sub_service_ids')
    def _onchange_sub_service_ids(self):
        """
        When products are added to sub_service_ids, corresponding lines are created
        in detail_ids based on x_concepts_ids of each product, avoiding duplicates.
        """
        if not self.sub_service_ids:
            self.detail_ids = [(5, 0, 0)]
            return

        # 1. Recopilar conceptos válidos de subservicios actuales
        valid_concept_ids = set(self.sub_service_ids.mapped('x_concepts_ids').ids)

        # 2. Eliminar líneas cuyos conceptos ya no están en los subservicios
        for line in self.detail_ids:
            product = line.product_id
            if product:
                c_id = product.id.origin or product.id if isinstance(product.id, models.NewId) else product.id
                if c_id and c_id not in valid_concept_ids:
                    self.detail_ids = [(3, line.id)]

        # 3. Get existing products in detail_ids handling NewIDs
        # We maintain your logic of iterating to find the real ID or origin
        existing_concept_ids = set()
        for line in self.detail_ids:
            product = line.product_id
            if product:
                # Maintain your precise NewID check
                c_id = product.id.origin or product.id if isinstance(product.id, models.NewId) else product.id
                if c_id:
                    existing_concept_ids.add(c_id)

        # 4. List to store new One2many commands
        new_lines = []

        # 5. Process each product in sub_service_ids
        for product in self.sub_service_ids:
            # 6. Check for configured concepts
            if product.x_concepts_ids:
                for concept in product.x_concepts_ids:
                    # Get real ID of the concept
                    concept_id = concept.id.origin or concept.id if isinstance(concept.id, models.NewId) else concept.id
                    # 7. Verify if concept already exists in the set
                    if concept_id and concept_id not in existing_concept_ids:
                        new_lines.append((0, 0, {
                            'product_id': concept_id,
                            'mandatory': True,
                        }))
                        # 8. Add to set immediately to prevent duplicates in the same loop
                        existing_concept_ids.add(concept_id)

        # 9. Update detail_ids adding the new records
        if new_lines:
            # We use your proven method to maintain existing lines and add new ones
            self.detail_ids = [(4, line.id) for line in self.detail_ids] + new_lines

    @api.constrains('membership_plan_id', 'service_id', 'sub_service_ids', 'vehicle_weight_category_id')
    def _check_unique_combination(self):
        for record in self:
            # 1. Prepare current sub-service IDs in a sorted list for exact set comparison
            current_sub_services = sorted(record.sub_service_ids.ids)
            current_weight = record.vehicle_weight_category_id.id or False

            # 2. Define search domain for matching base fields (Plan and Service)
            domain = [
                ('id', '!=', record.id),
                ('membership_plan_id', '=', record.membership_plan_id.id),
                ('service_id', '=', record.service_id.id),
            ]

            # Fetch existing records using search_read for better performance
            existing_records = self.search_read(domain, ['sub_service_ids', 'vehicle_weight_category_id'])

            for data in existing_records:
                # Sort existing sub-services to compare with current ones
                existing_sub_services = sorted(data['sub_service_ids'])

                # If the first 3 fields match (Plan + Service + Sub-services)
                if existing_sub_services == current_sub_services:
                    # Extract the ID from the Many2one tuple returned by search_read
                    existing_weight = data['vehicle_weight_category_id'][0] if data['vehicle_weight_category_id'] else False

                    # RULE 1: Prevent exact duplicates
                    if existing_weight == current_weight:
                        raise ValidationError(_(
                            'Duplicate found: An identical record already exists for this combination.'
                        ))

                    # RULE 2: Exclusivity Logic
                    # Prevents mixing a "General" rule (Weight is False) with "Specific" rules (Weight has value)
                    if (not current_weight and existing_weight) or (current_weight and not existing_weight):
                        raise ValidationError(_(
                            'Configuration Conflict: You cannot have a "General" rule (no weight) '
                            'and "Specific" rules (with weight) for the same service combination.'
                        ))

    @api.depends('service_id', 'sub_service_ids')
    def _compute_name(self):
        for rec in self:
            service_name = rec.service_id.name or ''
            products = ', '.join(rec.sub_service_ids.mapped('name'))
            rec.name = f"{service_name}: {products}" if service_name else products

    @api.depends('service_id')
    def _compute_x_service_domain(self):
        for rec in self:
            domain = []

            all_service_id = rec.env.ref('product.product_category_all')
            saleable_service_id = rec.env.ref('product.product_category_1')
            expense_service_id = rec.env.ref('product.cat_expense')

            domain = [
                ('disabled', '=', False),
                ('id', 'not in', [all_service_id.id, saleable_service_id.id, expense_service_id.id])
            ]

            rec.x_service_domain = domain

    @api.depends('service_id', 'sub_service_ids')
    def _compute_x_product_domain(self):
        for rec in self:
            # lines = rec.membership_plan_id.product_line_ids
            domain = [
                ('categ_id', '=', rec.service_id and rec.service_id.id),
                ('type', '=', 'service'),
                ('disabled', '=', False),
                # ('id', 'not in', lines and lines.mapped("sub_service_ids").ids or [])
            ]

            rec.x_product_domain = domain

    def action_save(self):
        self.sudo().write({
            'considerations_html': self.considerations_html,
            'exclusions_html': self.exclusions_html
        })
        return {'type': 'ir.actions.act_window_close'}

    def action_open_view_considerations_html(self):
        self.ensure_one()

        return {
            'name': _('Considerations'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.membership.plan.product.line',
            'view_mode': 'form',
            'views': [(self.env.ref('custom_nu.view_custom_membership_plan_product_considerations_html_form').id, 'form')],
            'target': 'new',
            'res_id': self.id,
            'domain': [('id', '=', self.id)],
            'context': dict(self.env.context),
        }

    def action_open_view_exclusions_html(self):
        self.ensure_one()

        return {
            'name': _('Exclusions'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.membership.plan.product.line',
            'view_mode': 'form',
            'views': [(self.env.ref('custom_nu.view_custom_membership_plan_product_exclusions_html_form').id, 'form')],
            'target': 'new',
            'res_id': self.id,
            'domain': [('id', '=', self.id)],
            'context': dict(self.env.context),
        }

    def action_back_to_coverage(self):
        self.ensure_one()

        return {
            'name': _('Coverage Details'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.membership.plan.product.line',
            'view_mode': 'kanban',
            'views': [[False, 'kanban']],
            'target': 'new',
            'domain': [('membership_plan_id', '=', self.membership_plan_id.id)],
            'context': {
                'group_by': ['service_id'],
                'create': False,
            },
        }


class CustomMembershipPlanLineLimit(models.Model):
    _name = 'custom.membership.plan.line.limit'
    _description = 'Subservice details for limit line'
    _sort = 'line_id, limit_coverage_min'

    line_id = fields.Many2one(
        'custom.membership.plan.product.line',
        string='Product Line',
        ondelete='cascade',
        required=True,
        index=True
    )
    limit_coverage_min = fields.Integer('Limit Coverage min (km)')
    limit_coverage_max = fields.Integer('Limit Coverage max (km)')
    amount = fields.Monetary(string='Amount ($)', default=0.0)
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id.id)


class CustomMembershipPlanLineProduct(models.Model):
    _name = 'custom.membership.plan.line.product'
    _description = 'Subservices details for product line'

    line_id = fields.Many2one(
        'custom.membership.plan.product.line',
        string='Product Line',
        ondelete='cascade',
        required=True,
        index=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Concepto',
        required=True,
        ondelete='restrict'
    )
    limit_coverage = fields.Float()
    limit_coverage_min = fields.Integer('Limit Coverage min (km)')
    limit_coverage_max = fields.Integer('Limit Coverage max (km)')
    cost = fields.Monetary(string='Amount ($)', default=0.0)
    quantity = fields.Integer(string='Quantity', default=0)
    x_concept_domain = fields.Binary(string="Concept domain", compute="_compute_x_concept_domain")
    coverage_type = fields.Selection([
        ('limited', 'Limited'),
        ('unlimited', 'Unlimited'),
    ])
    mandatory = fields.Boolean(default=False)
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id.id)

    # === COMPUTE METHODS === #
    @api.depends('product_id', 'line_id', 'line_id.sub_service_ids', 'line_id.detail_ids.product_id')
    def _compute_x_concept_domain(self):
        for rec in self:
            if not rec.line_id:
                rec.x_concept_domain = []
                continue

            # already_added_ids = rec.line_id.detail_ids.mapped('product_id').ids

            # Dominio de productos permitidos
            sub_service_ids = rec.line_id.sub_service_ids.ids or [0]
            service_id = rec.line_id.service_id.id

            domain = [
                ('sale_ok', '=', False),
                ('sh_product_subscribe', '=', False),
                ('purchase_ok', '=', True),
                ('x_concept_ok', '=', True),
                ('type', '=', 'service'),
                ('disabled', '=', False),
                ('list_price', '=', 0),
                ('uom_id', 'in', [
                    self.env.ref('uom.product_uom_km').id,
                    self.env.ref('uom.product_uom_day').id,
                    self.env.ref('uom.product_uom_hour').id,
                    self.env.ref('l10n_mx.product_uom_service_unit').id,
                    self.env.ref('uom.product_uom_unit').id,
                    self.env.ref('uom.product_uom_litre').id,
                ]),
                '|',
                ('x_apply_all_services_subservices', '=', True),
                ('x_categ_id', 'in', [service_id, False]),
                '|',
                ('x_product_id', 'in', sub_service_ids),
                ('x_product_id', '=', False),
                # ('id', 'not in', already_added_ids),
            ]

            rec.x_concept_domain = domain

    # Evitar duplicados por linea (opcional)
    _sql_constraints = [
        (
            'uniq_line_product',
            'unique(line_id, product_id, limit_coverage_min, limit_coverage_max, cost)',
            'El subservicio ya existe en esta línea.')
    ]
