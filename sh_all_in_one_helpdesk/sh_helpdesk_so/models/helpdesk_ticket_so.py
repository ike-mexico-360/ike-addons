# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields,_
from odoo.exceptions import ValidationError

class HelpdeskTicketSO(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    sh_sale_order_ids = fields.Many2many("sale.order", string="Orders")
    sale_order_count = fields.Integer(
        'Sales Order Count', compute='_compute_sale_order_count_helpdesk')

    def action_sale_create_order(self):
        context = {}
        if self.partner_id:
            context.update({
                'default_partner_id': self.partner_id.id,
            })
        if self.user_id:
            context.update({
                'default_user_id': self.user_id.id,
            })
        if self:
            context.update({
                'default_sh_sale_ticket_ids': [(6, 0, self.ids)],
            })

        if self.product_ids:
            order_id = self.env['sale.order'].create({
                'partner_id': self.partner_id.id,
                'user_id': self.user_id.id,
                'sh_sale_ticket_ids': self.ids})
            if order_id:
                line_list = []
                for product in self.product_ids:
                    line_vals = {
                        'product_template_id': product.product_tmpl_id.id,
                        'display_type': False,
                        'product_id': product.id,
                        'name': product.display_name,
                        'product_uom_qty': 1.0,
                        'price_unit': product.list_price,
                        'product_uom': product.uom_id.id,
                    }
                    if product.taxes_id:
                        line_vals.update(
                            {'tax_id': [(6, 0, product.taxes_id.ids)]})
                    line_list.append((0, 0, line_vals))
                order_id.order_line = line_list

            return {
                'name': 'Sale Order',
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'view_mode': 'form',
                'res_id': order_id.id,
                'target': 'new'
            }
        else:
            raise ValidationError(_('Please select product for create Sale Order'))

    def _compute_sale_order_count_helpdesk(self):
        for record in self:
            record.sale_order_count = 0
            tickets = self.env['sale.order'].search(
                [('id', 'in', record.sh_sale_order_ids.ids)], limit=None)
            record.sale_order_count = len(tickets.ids)

    def action_view_sale_orders(self):
        self.ensure_one()
        orders = self.env['sale.order'].search([
            ('id', 'in', self.sh_sale_order_ids.ids)
        ])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sale.action_orders")
        if len(orders) > 1:
            action['domain'] = [('id', 'in', orders.ids)]
        elif len(orders) == 1:
            form_view = [(self.env.ref('sale.view_order_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + \
                    [(state, view)
                     for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = orders.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
