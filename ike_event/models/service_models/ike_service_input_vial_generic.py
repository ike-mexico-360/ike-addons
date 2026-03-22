# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IkeServiceInputVialBase(models.AbstractModel):
    _name = 'ike.service.input.vial.base'
    _inherit = ['ike.service.input']
    _description = 'Service Input Vial Base'

    service_vehicle_type_domain = fields.Binary(compute='_compute_service_vehicle_type_domain')
    suggested_vehicle_types = fields.Json(
        string='Suggested Service Vehicle Types',
        default=lambda self: list(self.env['custom.vehicle.type'].search([]).mapped('name_capitalization')),
        copy=False,
    )
    service_accessories_domain = fields.Binary(compute='_compute_accessories_domain')
    suggested_accessories = fields.Json(
        string='Suggested Service Accessories',
        default=lambda self: list(
            self.env['product.product'].search(self.env['product.product'].get_accessories_domain()).mapped('id')),
        copy=False,
    )

    # === COMPUTE === #
    @api.depends('suggested_vehicle_types')
    def _compute_service_vehicle_type_domain(self):
        for rec in self:
            service_input = self.env['ike.service.input.vial'].search(
                [('event_id', '=', rec.event_id.id)], limit=1)
            vehicle_category_id = service_input.vehicle_category_id.id

            try:
                suggested_vehicle_types = list(set(
                    item['name'].upper() if isinstance(item, dict) else str(item)
                    for item in (rec.suggested_vehicle_types or [])
                ))
            except (TypeError, ValueError, KeyError):
                suggested_vehicle_types = []

            base_domain = [
                ('disabled', '=', False),
                # ('x_subservice_id', '=', rec.event_id.sub_service_id.id), # ToDo delete after test change to x_subservice_ids
                ('x_subservice_ids', 'in', [rec.event_id.sub_service_id.id]),
                ('x_service_id', '=', rec.event_id.service_id.id),
                ('subservice_specification_ids.vehicle_category_id', '=', vehicle_category_id),
            ]

            suggested_records = self.env['custom.vehicle.type'].search(
                base_domain + [('name_capitalization', 'in', suggested_vehicle_types)])

            suggested_ids = suggested_records.ids

            domain = ['|', ('id', 'in', suggested_ids),] + base_domain
            rec.service_vehicle_type_domain = domain

    @api.depends('suggested_accessories')
    def _compute_accessories_domain(self):
        for rec in self:
            base_domain = self.env['product.product'].get_accessories_domain()

            try:
                suggested_accessories = list(set(
                    item['id'] if isinstance(item, dict) else int(item)
                    for item in (rec.suggested_accessories or [])
                ))
            except (TypeError, ValueError, KeyError):
                suggested_accessories = []

            if suggested_accessories:
                rec.service_accessories_domain = ['|', ('id', 'in', suggested_accessories)] + base_domain
            else:
                rec.service_accessories_domain = base_domain


class IkeServiceInputVialTruck(models.Model):
    _name = 'ike.service.input.vial.generic'
    _inherit = ['ike.service.input.vial.base']
    _description = 'Service Input Vial Generic'

    tire_size = fields.Integer(default=15)
    is_highway = fields.Boolean(string='Is a Highway?')

    # IA Suggestion fields in base model
    service_vehicle_type_ids = fields.Many2many(
        'custom.vehicle.type',
        'ike_service_vial_generic_vehicle_type_rel', 'sub_service_id', 'vehicle_type_id',
        string='Service Vehicle Types', copy=False)
    service_accessory_ids = fields.Many2many(
        'product.product',
        'ike_service_vial_generic_accessories_rel',
        'sub_service_id', 'accessories_id',
        string='Accessories', copy=False)

    # === SUMMARY === #
    def set_event_summary_user_subservice_data(self):
        pass
