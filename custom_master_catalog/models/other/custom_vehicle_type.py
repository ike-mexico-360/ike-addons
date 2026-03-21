# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup


class CustomVehicleType(models.Model):
    _name = 'custom.vehicle.type'
    _description = 'Types Service Vehicles'
    _inherit = ['mail.thread']

    # === FIELDS === #
    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    name = fields.Char(string='Name', required=True, tracking=True)
    name_capitalization = fields.Char(string='Name capitalization', compute='_compute_name_capitalization', store=True)
    x_service_id = fields.Many2one(
        'product.category',
        'Service',
        domain="[('disabled', '=', False)]",
        tracking=True
    )
    x_subservice_id = fields.Many2one(
        'product.product',
        'Subservice',
        domain="[('disabled', '=', False), ('categ_id', '=', x_service_id)]",
        tracking=True)
    subservice_specification_ids = fields.Many2many(
        'custom.subservice.specification',
        'subservice_specification_vehicle_type_rel',
        'vehicle_type_id',
        'subservice_specification_id',
        string='Category specification',
        domain="[('disabled', '=', False), ('service_id', '=', x_service_id)]",
        tracking=True
    )

    x_categ_domain = fields.Binary(string="Service domain", compute="_compute_x_categ_domain")

    @api.depends('name')
    def _compute_x_categ_domain(self):
        for rec in self:
            domain = []
            if self._context.get('x_subservice_view', False):
                all_categ_id = self.env.ref('product.product_category_all')
                saleable_categ_id = self.env.ref('product.product_category_1')
                expense_categ_id = self.env.ref('product.cat_expense')
                domain = [('disabled', '=', False), ('id', 'not in', [all_categ_id.id, saleable_categ_id.id, expense_categ_id.id])]
            rec.x_categ_domain = domain

    @api.depends('name')
    def _compute_name_capitalization(self):
        for rec in self:
            rec.name_capitalization = rec.name.upper()

    # === ONCHANGE === #
    @api.onchange('x_service_id')
    def _onchange_x_service_id(self):
        self.x_subservice_id = False
        if self.x_service_id:
            categories = self.env['custom.subservice.specification'].search([
                ('disabled', '=', False),
                ('service_id', '=', self.x_service_id.id)
            ])
            self.subservice_specification_ids = categories
        else:
            self.subservice_specification_ids = False

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
