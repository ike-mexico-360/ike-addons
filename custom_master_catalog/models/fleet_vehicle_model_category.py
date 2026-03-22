# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup


class FleetVehicleModelCategory(models.Model):
    _inherit = ['fleet.vehicle.model.category', 'mail.thread']
    _name = 'fleet.vehicle.model.category'
    _description = 'Vehicle Category'

    # === FIELDS === #
    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    # Redefinition of 'name' to enable change tracking
    name = fields.Char(required=True, tracking=True)
    x_service_id = fields.Many2one(
        'product.category',
        'Service',
        domain="[('disabled', '=', False)]",
        tracking=True)

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
