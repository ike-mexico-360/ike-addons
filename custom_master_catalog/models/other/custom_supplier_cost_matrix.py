# -*- coding: utf-8 -*-

import re

from odoo import models, fields, tools, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomSupplierCostMatrix(models.Model):
    _name = 'custom.supplier.cost.matrix'
    _description = 'Supplier Cost Matrix'
    _inherit = ['mail.thread']
    _rec_name = 'supplier_center_id'

    supplier_center_id = fields.Many2one(
        comodel_name='res.partner', string='Center of attention',
        domain=[('parent_id.x_is_supplier', '=', True), ('type', '=', 'center'), ('disabled', '=', False)],
        ondelete='restrict', tracking=True)

    supplier_id = fields.Many2one(
        comodel_name='res.partner', string='Supplier',
        domain=[('x_is_supplier', '=', True), ('disabled', '=', False)], ondelete='restrict', tracking=True)

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)
    service_id = fields.Many2one(
        comodel_name='product.category', string='Service',
        domain=[('disabled', '=', False)], tracking=True)
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("closed", "Closed")],
        default='draft', string="Header state", tracking=True)
    x_state = fields.Selection(
        [("active", "Active"), ("inactive", "Inactive")],
        default='active', string="State", tracking=True)
    date_init = fields.Date(string='Date init', default=fields.Date.context_today, tracking=True)
    date_end = fields.Date(string='Date end', tracking=True)

    cost_product_ids = fields.One2many(
        comodel_name='custom.supplier.cost.product',
        inverse_name='supplier_cost_matrix_id',
        string='Product cost', tracking=True)

    # === ONCHANGE === #
    @api.onchange("supplier_center_id")
    def _onchange_supplier_id(self):
        """Set fields from supplier_center_id."""
        if self.supplier_center_id and self.supplier_center_id.parent_id:
            self.supplier_id = self.supplier_center_id.parent_id.id

    # === ACTIONS === #
    def action_disable(self, reason=None):
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
            self.message_post(
                body=body,
                message_type='notification',
                body_is_html=True)
        return super().action_disable(reason)

    def action_confirm(self):
        for rec in self:
            rec.state = "confirmed"


class CustomSupplierCostProduct(models.Model):
    _name = 'custom.supplier.cost.product'
    _description = 'Supplier Cost Product'
    _rec_name = 'product_id'

    supplier_cost_matrix_id = fields.Many2one(
        "custom.supplier.cost.matrix", string='Supplier Cost Matrix', ondelete='cascade')
    service_id = fields.Many2one(related='supplier_cost_matrix_id.service_id', string='Service', sub_tracking=True)
    product_id = fields.Many2one('product.product', string='Subservice', sub_tracking=True)
    state_id = fields.Many2one('res.country.state', string='State', sub_tracking=True)
    geographical_area_id = fields.Many2one('custom.state.municipality', string='Geographical area', sub_tracking=True)
    type_event_id = fields.Many2one('custom.type.event', string='Event type')
    vehicle_category_id = fields.Many2one('fleet.vehicle.model.category', string='Category', sub_tracking=True)
    account_id = fields.Many2one(
        comodel_name='res.partner',
        string='Account',
        domain=[('x_is_account', '=', True)],
        sub_tracking=True)
    cost = fields.Float(string='Cost', sub_tracking=True)
    holiday_date_applies = fields.Boolean(string="Holiday date applies", sub_tracking=True)
    high_risk_area = fields.Boolean(related="geographical_area_id.red_zone", string="High risk area", sub_tracking=True)
    active_agreement = fields.Boolean(string="Active agreement", sub_tracking=True)
    supplier_status_id = fields.Many2one('custom.supplier.types.statuses', string='Supplier status', sub_tracking=True)
