# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, Command, api, _
from odoo.exceptions import ValidationError, UserError
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

    @api.model
    def get_can_be_disabled(self):
        """ Inherit and override to restrict disabling capabilities based on specific user groups. """
        res = super().get_can_be_disabled()
        # List of allowed technical group XML IDs
        allowed_groups = [
            'base.group_system',
        ]
        has_permission = any(self.env.user.has_group(group) for group in allowed_groups)
        if not has_permission:
            return False
        return res

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
        is_assigned_user = self.assigned_user_id.id == self.env.user.id
        is_admin_user = self.env.user.has_group('base.group_system')

        if not (is_assigned_user or is_admin_user):
            raise ValidationError(_('Only the assigned user or the administrator can validate prices'))

        sum_cost_price = sum(self.selected_supplier_ids.supplier_product_ids.filtered(
            lambda x: not x.display_type).mapped('cost_price'))
        sum_base_cost_price = sum(self.selected_supplier_ids.supplier_product_ids.filtered(
            lambda x: not x.display_type).mapped('base_cost_price'))

        if sum_base_cost_price > sum_cost_price:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Cost confirmation'),
                'res_model': 'ike.event.confirm.costs.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'default_event_id': self.id},
            }

        self.sudo().action_close()

    def action_create_purchase_orders(self):
        for rec in self:
            if not rec.x_purchase_ids:
                purchase_ids = rec._x_create_grouped_purchase_orders()
                for purchase in purchase_ids:
                    purchase.action_rfq_send_one_step()
                    supplier_ids = rec.selected_supplier_ids.filtered(lambda x: x.supplier_id.id == purchase.partner_id.id)
                    supplier_cancelled = all(
                        supplier.state in ['cancel', 'cancel_event', 'cancel_supplier']
                        for supplier in supplier_ids
                    )
                    supplier_reason_from_supplier = all(
                        supplier.cancel_reason_id.from_supplier
                        for supplier in supplier_ids
                    )

                    if supplier_cancelled and supplier_reason_from_supplier and purchase.amount_untaxed == 0:
                        purchase.button_confirm()

    def x_get_values_for_purchase_line(self, supplier_product_id):
        return {
            "name": supplier_product_id.product_id.name,
            "product_id": supplier_product_id.product_id.id,
            "product_qty": supplier_product_id.base_quantity,
            "price_unit": supplier_product_id.base_unit_price,
            "x_base_unit_price": supplier_product_id.base_unit_price,
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

        membership_plan_id = selected_supplier_id.event_id.user_membership_id.membership_plan_id
        account_id = membership_plan_id.account_id
        x_invoice_company_id = account_id.x_invoice_company_id[0].id if account_id.x_invoice_company_id else False

        company_id = self.env.company
        if not company_id.x_default_purchase_project_id:
            raise UserError(_("No default purchase project has been configured for this company."))

        return {
            "partner_id": supplier_id.id,
            "company_id": company_id.id,
            "x_event_id": self.id,  # Link to event_id
            "x_sub_service_id": selected_supplier_id.event_id.sub_service_id.id,
            "x_nu_user_id": selected_supplier_id.event_id.user_id.id,
            "x_customer_id": account_id.parent_id.id,
            "x_membership_plan_id": membership_plan_id.id,
            "x_invoice_company_id": x_invoice_company_id,
            "date_order": fields.Datetime.now() + timedelta(hours=max_hours_to_confirm),
            "project_id": company_id.x_default_purchase_project_id.id,
        }
