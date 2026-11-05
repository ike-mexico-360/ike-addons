# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class IkeEvenPhoneWizard(models.Model):
    _name = 'ike.event.add.supplier.wizard'
    _description = 'Event Add Supplier Wizard'

    event_id = fields.Many2one('ike.event', required=True, readonly=True)
    supplier_id = fields.Many2one('res.partner', required=True)
    supplier_domain = fields.Binary(compute='_compute_supplier_domain')
    supplier_number = fields.Integer(readonly=True)
    aux_truck_id = fields.Many2one('fleet.vehicle', 'Service Vehicle', required=True)
    aux_truck_domain = fields.Binary(compute='_compute_aux_truck_domain')

    @api.depends('event_id', 'event_id.sub_service_id')
    def _compute_supplier_domain(self):
        for rec in self:
            service_input = self.env[rec.event_id.service_res_model].browse(rec.event_id.service_res_id)
            state = service_input.state_id or service_input.municipality_id.state_id  # type: ignore

            domain = [
                ('x_is_supplier', '=', True),
                ('disabled', '=', False),
                ('child_ids', 'any', [
                    ('type', '=', 'center'),
                    ('disabled', '=', False),
                    ('x_geographical_area_ids', 'any', [
                        ('state_id', '=', state.id),
                        ('active', '=', True),
                        ('disabled', '=', False),
                        ('area_product_ids', 'any', [
                            ('product_id', '=', rec.event_id.sub_service_id.id),
                            ('disabled', '=', False),
                        ]),
                    ]),
                ]),
            ]
            rec.supplier_domain = domain

    @api.depends('event_id', 'supplier_id')
    def _compute_aux_truck_domain(self):
        for rec in self:
            domain = rec._get_aux_truck_base_domain()

            if rec.aux_truck_id:
                domain = expression.OR([domain, [('id', '=', rec.aux_truck_id.id)]])

            rec.aux_truck_domain = domain

    @api.onchange('supplier_id')
    def _onchange_supplier_id_aux_truck(self):
        # Default: first vehicle by state priority (available > in_service > not_available)
        for rec in self:
            if not rec.supplier_id:
                rec.aux_truck_id = False
                continue
            rec.aux_truck_id = self.env['fleet.vehicle'].search(
                rec._get_aux_truck_base_domain(), order=self.env['fleet.vehicle']._aux_truck_order, limit=1)

    def action_create_event_supplier_link(self):
        self.ensure_one()
        if not self.aux_truck_id:
            return

        supplier_link_id = self.event_id.service_supplier_link_ids.filtered(
            lambda x:
                x.supplier_id.id == self.supplier_id.id
                and x.supplier_number == self.supplier_number,
        )

        # Supplier Link
        if not supplier_link_id:
            supplier_link_id = self.env['ike.event.supplier.link'].with_context(from_internal=True).create({
                'event_id': self.event_id.id,
                'supplier_id': self.supplier_id.id,
                'supplier_number': self.supplier_number,
                'aux_truck_id': self.aux_truck_id.id
            })
            supplier_link_id.action_set_products()

        event_supplier_id = self.event_id.add_manual_supplier(self.supplier_id, self.aux_truck_id, supplier_link_id)

        return event_supplier_id.action_view_products()

    def _get_aux_truck_base_domain(self):
        self.ensure_one()
        sub_res_id = self.env[self.event_id.sub_service_res_model].browse(self.event_id.sub_service_res_id)
        service_vehicle_type_ids = []
        service_vehicle_type_ids = sub_res_id.service_vehicle_type_ids.ids  # type: ignore

        domain = [
            ('disabled', '=', False),
            ('x_vehicle_service_state', 'in', ['available', 'in_service', 'not_available']),
            ('x_vehicle_type', 'in', service_vehicle_type_ids),
            ('x_partner_id', '=', self.supplier_id.id),
            ('x_subservice_ids', 'in', [self.event_id.sub_service_id.id]),
            ('driver_id', '!=', False),
        ]

        if self.event_id.requires_federal_plates:
            domain.append(
                ('x_federal_license_plates', '=', True),
            )

        # if self.event_id:
        #     trucks_used = self.event_id.service_supplier_ids.mapped('truck_id').ids
        #     if trucks_used:
        #         domain.append(('id', 'not in', trucks_used))

        return domain
