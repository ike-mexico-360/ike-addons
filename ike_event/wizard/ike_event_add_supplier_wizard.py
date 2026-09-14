# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _
from odoo.osv import expression


class IkeEvenPhoneWizard(models.Model):
    _name = 'ike.event.add.supplier.wizard'
    _description = 'Event Add Supplier Wizard'

    event_id = fields.Many2one('ike.event', required=True, readonly=True)
    supplier_id = fields.Many2one('res.partner', required=True, domain="[('x_is_supplier', '=', True)]")
    supplier_number = fields.Integer(readonly=True)
    aux_truck_id = fields.Many2one('fleet.vehicle', 'Service Vehicle', required=True)
    aux_truck_domain = fields.Binary(compute='_compute_aux_truck_domain')

    @api.depends('event_id', 'supplier_id')
    def _compute_aux_truck_domain(self):
        for rec in self:
            sub_res_id = self.env[rec.event_id.sub_service_res_model].browse(rec.event_id.sub_service_res_id)
            service_vehicle_type_ids = []
            service_vehicle_type_ids = sub_res_id.service_vehicle_type_ids.ids  # type: ignore

            domain = [
                ('disabled', '=', False),
                ('x_vehicle_service_state', '=', 'available'),
                ('x_vehicle_type', 'in', service_vehicle_type_ids),
                ('x_partner_id', '=', rec.supplier_id.id),
                ('x_subservice_ids', 'in', [rec.event_id.sub_service_id.id]),
                ('driver_id', '!=', False),
            ]

            if rec.event_id.requires_federal_plates:
                domain.append(
                    ('x_federal_license_plates', '=', True),
                )

            # if rec.event_id:
            #     trucks_used = rec.event_id.service_supplier_ids.mapped('truck_id').ids
            #     if trucks_used:
            #         domain.append(('id', 'not in', trucks_used))

            if rec.aux_truck_id:
                domain = expression.OR([domain, [('id', '=', rec.aux_truck_id.id)]])

            rec.aux_truck_domain = domain

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
