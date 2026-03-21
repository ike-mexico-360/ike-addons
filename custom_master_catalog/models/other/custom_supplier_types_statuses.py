# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomSupplierTypesStatuses(models.Model):
    _name = 'custom.supplier.types.statuses'
    _description = 'Types Of Supplier Statuses'
    _inherit = ['mail.thread']

    # === FIELDS ===
    active = fields.Boolean('Active', default=True, tracking=True)
    ref = fields.Char('')
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    name = fields.Char('Name', required=True, tracking=True)
    description = fields.Text('Description', size=300, tracking=True)
    x_service_id = fields.Many2one(
        'product.category',
        'Service',
        required=True,
        domain="[('disabled', '=', False)]",
        tracking=True
    )
    affects_costs = fields.Boolean('Affects costs', default=False, tracking=True)

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

    # === CONSTRAINT METHODS === #
    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('id', '!=', rec.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_('A record with the same name already exists.'))

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
