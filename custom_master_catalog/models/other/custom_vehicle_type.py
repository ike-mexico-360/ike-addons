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
    x_vehicle_category_id = fields.Many2many(
        'fleet.vehicle.model.category',
        string='Category',
        domain="[('disabled', '=', False), ('x_service_id', '=', x_service_id)]",
        tracking=True
    )

    # === ONCHANGE === #
    @api.onchange('x_service_id')
    def _onchange_x_service_id(self):
        self.x_subservice_id = False
        if self.x_service_id:
            categories = self.env['fleet.vehicle.model.category'].search([
                ('disabled', '=', False),
                ('x_service_id', '=', self.x_service_id.id)
            ])
            self.x_vehicle_category_id = categories
        else:
            self.x_vehicle_category_id = False

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
