# -*- coding: utf-8 -*-
from odoo import models, fields, _
from markupsafe import Markup


class CustomSupplierTypesStatuses(models.Model):
    _name = 'custom.supplier.types.statuses'
    _description = 'Types Of Supplier Statuses'
    _inherit = ['mail.thread']

    # === FIELDS ===
    active = fields.Boolean('Active', default=True, tracking=True)
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
