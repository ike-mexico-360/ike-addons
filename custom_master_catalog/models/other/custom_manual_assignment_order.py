# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CustomManualAssignmentOrder(models.Model):
    _name = 'custom.manual.assignment.order'
    _description = 'Manual Assignment Order'
    _order = 'state_id, municipality_id, product_id, sequence, id'

    sequence = fields.Integer(string='Manual Assignment Order', default=1, required=True)
    state_id = fields.Many2one(
        'res.country.state',
        string='State',
        required=True,
        domain="[('country_id.code', '=', 'MX'), ('active', '=', True)]",
        ondelete='restrict',
    )
    municipality_id = fields.Many2one(
        'custom.state.municipality',
        string='Geographical Zone',
        required=True,
        domain="[('state_id', '=', state_id), ('active', '=', True), ('disabled', '=', False)]",
        ondelete='restrict',
    )
    product_id = fields.Many2one(
        'product.product',
        string='Subservice',
        required=True,
        domain="[('type', '=', 'service'), ('disabled', '=', False)]",
        ondelete='restrict',
    )
    supplier_center_id = fields.Many2one(
        'res.partner',
        string='Care Center',
        required=True,
        domain="[('type', '=', 'center'), ('disabled', '=', False), ('parent_id.x_is_manual', '=', True)]",
        ondelete='cascade',
    )
    supplier_id = fields.Many2one(
        'res.partner',
        related='supplier_center_id.parent_id',
        string='Supplier',
        store=True,
    )

    _sql_constraints = [
        (
            'manual_assignment_order_unique',
            'unique(state_id, municipality_id, product_id, supplier_center_id)',
            'The care center can only have one manual assignment order per geographical zone and subservice.',
        ),
        (
            'manual_assignment_order_positive',
            'CHECK(sequence > 0)',
            'The manual assignment order must be greater than zero.',
        ),
    ]

    @api.model
    def get_manual_assignment_options(self):
        mexico = self.env.ref('base.mx')
        states = self.env['res.country.state'].search([
            ('country_id', '=', mexico.id),
            ('active', '=', True),
        ]).filtered(lambda state: not state.disabled).sorted('name')
        coverage_lines = self.env['custom.geographical.area.product.rel'].search([
            ('geographical_area_id.parent_id.x_is_manual', '=', True),
            ('geographical_area_id.parent_id.active', '=', True),
            ('geographical_area_id.parent_id.disabled', '=', False),
            ('geographical_area_id.active', '=', True),
            ('geographical_area_id.disabled', '=', False),
            ('product_id.disabled', '=', False),
            ('active', '=', True),
            ('disabled', '=', False),
        ])
        products = coverage_lines.mapped('product_id').sorted(
            key=lambda product: product.display_name or ''
        )
        return {
            'states': [
                {'id': state.id, 'name': state.name}
                for state in states
            ],
            'products': [
                {'id': product.id, 'name': product.display_name}
                for product in products
            ],
        }

    @api.model
    def get_manual_assignment_zones(self, state_id):
        if not state_id:
            return []
        zones = self.env['custom.state.municipality'].search([
            ('state_id', '=', state_id),
            ('active', '=', True),
            ('disabled', '=', False),
        ], order='name')
        return [{'id': zone.id, 'name': zone.name} for zone in zones]

    @api.model
    def get_manual_assignment_candidates(self, state_id, municipality_id, product_id):
        if not state_id or not municipality_id or not product_id:
            return []

        coverage_lines = self.env['custom.geographical.area.product.rel'].search([
            ('geographical_area_id.state_id', '=', state_id),
            ('geographical_area_id.municipality_id', '=', municipality_id),
            ('geographical_area_id.parent_id.x_is_manual', '=', True),
            ('geographical_area_id.parent_id.active', '=', True),
            ('geographical_area_id.parent_id.disabled', '=', False),
            ('geographical_area_id.partner_id.active', '=', True),
            ('geographical_area_id.partner_id.disabled', '=', False),
            ('geographical_area_id.active', '=', True),
            ('geographical_area_id.disabled', '=', False),
            ('product_id', '=', product_id),
            ('active', '=', True),
            ('disabled', '=', False),
        ])
        configured_orders = {
            record.supplier_center_id.id: record
            for record in self.search([
                ('state_id', '=', state_id),
                ('municipality_id', '=', municipality_id),
                ('product_id', '=', product_id),
            ])
        }
        candidates = {}
        for coverage in coverage_lines:
            center = coverage.geographical_area_id.partner_id
            supplier = center.parent_id
            configured = configured_orders.get(center.id)
            priority = int(coverage.priority or 0)
            candidates[center.id] = {
                'id': configured.id if configured else False,
                'supplier_center_id': center.id,
                'supplier': supplier.display_name,
                'supplier_center': center.display_name,
                'priority': priority,
                'sequence': configured.sequence if configured else 2147483647,
                'configured': bool(configured),
            }

        rows = sorted(
            candidates.values(),
            key=lambda row: (
                not row['configured'],
                row['sequence'],
                -row['priority'],
                row['supplier'],
                row['supplier_center'],
            ),
        )
        for sequence, row in enumerate(rows, start=1):
            row['sequence'] = sequence
        return rows

    @api.model
    def save_manual_assignment_order(
        self, state_id, municipality_id, product_id, supplier_rows
    ):
        if not state_id or not municipality_id or not product_id:
            raise ValidationError(_('State, geographical zone and subservice are required.'))

        valid_candidates = self.get_manual_assignment_candidates(
            state_id, municipality_id, product_id
        )
        valid_center_ids = {
            candidate['supplier_center_id'] for candidate in valid_candidates
        }
        requested_center_ids = list(dict.fromkeys(
            row.get('supplier_center_id') for row in supplier_rows
        ))
        if any(center_id not in valid_center_ids for center_id in requested_center_ids):
            raise ValidationError(_(
                'One or more care centers do not belong to suppliers configured for manual assignment.'
            ))

        priorities = {}
        for row in supplier_rows:
            center_id = row.get('supplier_center_id')
            priority = int(row.get('priority') or 0)
            if priority not in range(4):
                raise ValidationError(_('Priority must be between zero and three.'))
            priorities[center_id] = str(priority)

        coverage_lines = self.env['custom.geographical.area.product.rel'].search([
            ('geographical_area_id.state_id', '=', state_id),
            ('geographical_area_id.municipality_id', '=', municipality_id),
            ('geographical_area_id.partner_id', 'in', requested_center_ids),
            ('product_id', '=', product_id),
            ('active', '=', True),
            ('disabled', '=', False),
        ])
        for coverage in coverage_lines:
            coverage.priority = priorities[coverage.geographical_area_id.partner_id.id]

        self.search([
            ('state_id', '=', state_id),
            ('municipality_id', '=', municipality_id),
            ('product_id', '=', product_id),
        ]).unlink()
        self.create([
            {
                'state_id': state_id,
                'municipality_id': municipality_id,
                'product_id': product_id,
                'supplier_center_id': center_id,
                'sequence': sequence,
            }
            for sequence, center_id in enumerate(requested_center_ids, start=1)
        ])
        return True

    @api.constrains('state_id', 'municipality_id', 'product_id', 'supplier_center_id')
    def _check_manual_supplier(self):
        for record in self:
            supplier = record.supplier_center_id.parent_id
            if not supplier.x_is_manual:
                raise ValidationError(
                    _('Only suppliers configured for manual assignment can be added.')
                )
