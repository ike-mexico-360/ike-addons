# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, Command, api, _

import logging
_logger = logging.getLogger(__name__)


class IkeEvent(models.Model):
    _inherit = 'ike.event'

    x_purchase_ids = fields.One2many(
        comodel_name='purchase.order', inverse_name='x_event_id', string='Purchases', readonly=True)
    x_purchase_ids_count = fields.Integer(compute='_compute_x_purchase_ids_count', string='Purchases Count')

    x_ticket_ids = fields.One2many(
        comodel_name='sh.helpdesk.ticket', inverse_name='x_event_id', string='Ticket', readonly=True)
    x_ticket_ids_count = fields.Integer(compute='_compute_x_ticket_ids_count', string='Tickets Count')

    @api.depends('x_purchase_ids')
    def _compute_x_purchase_ids_count(self):
        for rec in self:
            rec.x_purchase_ids_count = len(rec.x_purchase_ids)

    @api.depends('x_ticket_ids')
    def _compute_x_ticket_ids_count(self):
        for rec in self:
            rec.x_ticket_ids_count = len(rec.x_ticket_ids)

    # ACTIONS
    def x_action_view_purchases(self):
        self.ensure_one()
        return {
            'name': self.name,
            'view_mode': 'list,form',
            'res_model': 'purchase.order',
            'views': [
                (self.env.ref('purchase.purchase_order_kpis_tree').id, 'list'),
                (self.env.ref('purchase.purchase_order_form').id, 'form')
            ],
            'type': 'ir.actions.act_window',
            'domain': [('x_event_id', '=', self.id)],
            'target': 'current',
        }

    def x_action_view_tickets(self):
        self.ensure_one()
        action = {
            'name': self.name,
            'view_mode': 'form,list',
            'res_model': 'sh.helpdesk.ticket',
            'views': [
                (self.env.ref('sh_all_in_one_helpdesk.sh_helpdesk_ticket_tree_view').id, 'list'),
                (self.env.ref('sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view').id, 'form')
            ],
            'type': 'ir.actions.act_window',
            'domain': [('x_event_id', '=', self.id)],
            'target': 'current',
        }
        if self.x_ticket_ids_count == 1:
            action['views'] = [(self.env.ref('sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view').id, 'form')]
            action['view_mode'] = 'form'
            action['res_id'] = self.x_ticket_ids[:1].id
            return action
        return action

    def _x_prepare_grouped_purchase_vals(self):
        self.ensure_one()
        grouped_purchase_by_suppliers = {}

        for supplier_line in self.selected_supplier_ids:
            product_ids = supplier_line.supplier_link_id.supplier_product_ids.filtered(
                lambda p: p.product_id
            )

            if not product_ids:
                continue

            if supplier_line.is_generic_supplier and supplier_line.purchase_supplier_id:
                selected_supplier = supplier_line.purchase_supplier_id
            else:
                selected_supplier = supplier_line.supplier_id

            if selected_supplier.id not in grouped_purchase_by_suppliers:
                grouped_purchase_by_suppliers[selected_supplier.id] = {
                    **self.x_get_values_for_purchase_header(supplier_line),
                    "order_line": [
                        Command.create({
                            'display_type': 'line_section',
                            'name': _('Concepts in coverage'),
                            'x_mandatory': True,
                            'x_covered': True,
                            'sequence': 1,
                            'product_qty': 0,
                            'x_product_qty_dispute': 0
                        }),
                        Command.create({
                            'display_type': 'line_section',
                            'name': _('Concepts out of coverage'),
                            'x_mandatory': True,
                            'x_covered': True,
                            'sequence': 1001,
                            'product_qty': 0,
                            'x_product_qty_dispute': 0
                        }),
                    ]
                }
            for concept_id in product_ids:
                grouped_purchase_by_suppliers[selected_supplier.id]['order_line'].append(
                    Command.create(self.x_get_values_for_purchase_line(concept_id))
                )

        return list(grouped_purchase_by_suppliers.values())

    def _x_create_grouped_purchase_orders(self):
        self.ensure_one()
        purchase_vals_list = self._x_prepare_grouped_purchase_vals()
        if not purchase_vals_list:
            return self.env['purchase.order']

        return self.env['purchase.order'].with_context(
            ike_event_purchase=True
        ).create(purchase_vals_list)

    def action_confirm_costs(self):
        """ Confirm Costs only close the event. For now. """
        self.sudo().action_close()

    def action_create_purchase_orders(self):
        for rec in self:
            if not rec.x_purchase_ids:
                purchase_ids = rec._x_create_grouped_purchase_orders()
                for purchase in purchase_ids:
                    purchase.action_rfq_send_one_step()

    def x_get_values_for_purchase_line(self, supplier_product_id):
        return {
            "name": supplier_product_id.product_id.name,
            "product_id": supplier_product_id.product_id.id,
            "product_qty": supplier_product_id.quantity,
            "price_unit": supplier_product_id.base_unit_price,
            "currency_id": self.env.company.currency_id.id,
            "x_supplier_product_id": supplier_product_id.id,  # Link to supplier_product_id
            "x_covered": supplier_product_id.covered,
            "sequence": supplier_product_id.sequence,
            "x_generated_from_event": True,  # To mark the line as generated from event
            "x_mandatory": True,
        }

    def x_get_values_for_purchase_header(self, selected_supplier_id):
        max_hours_to_confirm = self.env.company.x_time_for_automatic_purchase_generation

        if selected_supplier_id.is_generic_supplier and selected_supplier_id.purchase_supplier_id:
            supplier_id = selected_supplier_id.purchase_supplier_id
        else:
            supplier_id = selected_supplier_id.supplier_id

        return {
            "partner_id": supplier_id.id,
            "company_id": self.env.company.id,
            "x_event_id": self.id,  # Link to event_id
            "x_sub_service_id": selected_supplier_id.event_id.sub_service_id.id,
            "x_nu_user_id": selected_supplier_id.event_id.user_id.id,
            "x_membership_plan_id": selected_supplier_id.event_id.user_membership_id.membership_plan_id.id,
            "date_order": fields.Datetime.now() + timedelta(hours=max_hours_to_confirm),
        }
