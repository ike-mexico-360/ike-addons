# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, Command, api

import logging
_logger = logging.getLogger(__name__)


class IkeEvent(models.Model):
    _inherit = 'ike.event'

    x_purchase_ids = fields.One2many(
        comodel_name='purchase.order', inverse_name='x_event_id', string='Purchases', readonly=True)
    x_purchase_ids_count = fields.Integer(compute='_compute_x_purchase_ids_count', string='Purchases Count')

    @api.depends('x_purchase_ids')
    def _compute_x_purchase_ids_count(self):
        for rec in self:
            rec.x_purchase_ids_count = len(rec.x_purchase_ids)

    # ACTIONS
    def x_action_view_purchases(self):
        self.ensure_one()
        return {
            'name': self.name,
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'views': [(self.env.ref('purchase.purchase_order_kpis_tree').id, 'list'), (self.env.ref('purchase.purchase_order_form').id, 'form')],
            'type': 'ir.actions.act_window',
            'domain': [('x_event_id', '=', self.id)],
            'target': 'current',
        }

    def action_create_purchase_orders(self):
        self.ensure_one()
        # Cuando el evento esté en concluido
        if self.stage_ref == 'completed' and len(self.x_purchase_ids) == 0:
            # * Crear una sola orden de compra por proveedor con todos los conceptos
            grouped_purchase_by_suppliers = {}
            for supplier_line in self.selected_supplier_ids:
                product_ids = supplier_line.supplier_link_id.supplier_product_ids.filtered(
                    lambda x: x.product_id and x.unit_price > 0
                )
                if len(product_ids) == 0:  # Omitir crear RFQ para proveedores sin conceptos
                    continue
                if supplier_line.supplier_id.id not in grouped_purchase_by_suppliers:
                    grouped_purchase_by_suppliers[supplier_line.supplier_id.id] = {
                        **self.x_get_values_for_purchase_header(supplier_line),
                        "order_line": []
                    }
                for concept_id in product_ids:
                    grouped_purchase_by_suppliers[supplier_line.supplier_id.id]['order_line'].append(
                        Command.create(self.x_get_values_for_purchase_line(concept_id))
                    )

            self.env['purchase.order'].with_context(dict(ike_event_purchase=True)).create([
                purchase_vals for purchase_vals in grouped_purchase_by_suppliers.values()
            ])

    def x_get_values_for_purchase_line(self, supplier_product_id):
        return {
            "name": supplier_product_id.product_id.name,
            "product_id": supplier_product_id.product_id.id,
            "product_qty": supplier_product_id.quantity,
            "price_unit": supplier_product_id.unit_price,
            "currency_id": self.env.company.currency_id.id,
            "x_supplier_product_id": supplier_product_id.id,  # Link to supplier_product_id
            "x_generated_from_event": True,  # To mark the line as generated from event
        }

    def x_get_values_for_purchase_header(self, selected_supplier_id):
        max_hours_to_confirm = self.env.company.x_time_for_automatic_purchase_generation
        return {
            "partner_id": selected_supplier_id.supplier_id.id,
            "company_id": self.env.company.id,
            "x_event_id": self.id,  # Link to event_id
            "x_sub_service_id": selected_supplier_id.event_id.sub_service_id.id,
            "x_membership_plan_id": selected_supplier_id.event_id.user_membership_id.membership_plan_id.id,
            "date_order": fields.Datetime.now() + timedelta(hours=max_hours_to_confirm),
        }
