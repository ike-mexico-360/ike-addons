# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomSubserviceSpecification(models.Model):
    _name = 'custom.subservice.specification'
    _description = 'Subservice specification'
    _inherit = ['mail.thread']

    name = fields.Char('Name', required=True, tracking=True)
    service_id = fields.Many2one(
        'product.category',
        'Service',
        required=True,
        domain="[('disabled', '=', False)]",
        tracking=True)
    vehicle_category_id = fields.Many2one(
        'fleet.vehicle.model.category',
        'Category',
        domain="[('disabled', '=', False), ('x_service_id', '=', service_id)]",
        tracking=True)
    all_subservice = fields.Boolean('All subservices', default=False, tracking=True)
    subservice_ids = fields.Many2many(
        'product.product',
        'subservice_subservice_specification_rel',
        'subservice_specification_id',
        'subservice_id',
        'Subservice',
        domain="[('disabled', '=', False), ('categ_id', '=', service_id)]",
        tracking=True)
    x_categ_domain = fields.Binary(string="Service domain", compute="_compute_x_categ_domain")

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

    # === CONSTRAINT METHODS === #
    @api.constrains('name', 'service_id', 'subservice_ids')
    def _check_unique_name(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('service_id', '=', rec.service_id.id if rec.service_id else False),
                ('id', '!=', rec.id)
            ]

            if self.search_count(domain) > 0:
                raise ValidationError(_(
                    'A specification with the name "%s" already exists for this Service'
                ) % rec.name)

    # === COMPUTE METHODS === #
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

    # === ONCHANGE === #
    @api.onchange('subservice_ids')
    def _onchange_subservice_id(self):
        for rec in self:
            if not rec.service_id:
                rec.all_subservice = False
                return

            all_subservices = self.env['product.product'].search([
                ('disabled', '=', False),
                ('categ_id', '=', rec.service_id.id),
            ])

            if set(rec.subservice_ids.ids) != set(all_subservices.ids):
                rec.all_subservice = False

    @api.onchange('all_subservice', 'service_id')
    def _onchange_all_subservice(self):
        for rec in self:
            if not rec.service_id:
                rec.subservice_ids = [(5, 0, 0)]
                rec.all_subservice = False
                return

            all_subservices = self.env['product.product'].search([
                ('disabled', '=', False),
                ('categ_id', '=', rec.service_id.id),
            ])

            if rec.all_subservice:
                rec.subservice_ids = [(6, 0, all_subservices.ids)]
            else:
                if set(rec.subservice_ids.ids) == set(all_subservices.ids):
                    rec.subservice_ids = [(5, 0, 0)]

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
