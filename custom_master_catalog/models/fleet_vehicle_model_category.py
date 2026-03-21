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
