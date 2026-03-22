# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields,_
from odoo.exceptions import ValidationError


class HelpdeskTicketPO(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    sh_purchase_order_ids = fields.Many2many("purchase.order", string="Orders ")
    purchase_order_count = fields.Integer(
        'Purchase Order', compute='_compute_purchase_order_count_helpdesk')

    def action_create_purchase_order(self):
        context = {'date_planned': fields.Datetime.now()}
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
                'default_sh_purchase_ticket_ids': [(6, 0, self.ids)],
            })
        if self.product_ids:
            purchase_order_id = self.env['purchase.order'].create({
                'partner_id': self.partner_id.id,
                'user_id': self.user_id.id,
                'sh_purchase_ticket_ids': self.ids})
            if purchase_order_id:
                line_list = []
                for product in self.product_ids:
                    line_vals = {
                        'product_id': product.id,
                        'name': product.display_name,
                        'product_qty': 1.0,
                        'price_unit': product.standard_price,
                        'product_uom': product.uom_id.id,
                        'date_planned': fields.Datetime.now()
                    }
                    if product.taxes_id:
                        line_vals.update(
                            {'taxes_id': [(6, 0, product.taxes_id.ids)]})
                    line_list.append((0, 0, line_vals))
                purchase_order_id.order_line = line_list
            return {
                'name': 'Purchase Order',
                'type': 'ir.actions.act_window',
                'res_model': 'purchase.order',
                'view_mode': 'form',
                'res_id': purchase_order_id.id,
                'target': 'new'
            }
        else:
            raise ValidationError(_('Please select product for create Purchase Order'))

    def _compute_purchase_order_count_helpdesk(self):
        for record in self:
            record.purchase_order_count = 0
            tickets = self.env['purchase.order'].search(
                [('id', 'in', record.sh_purchase_order_ids.ids)], limit=None)
            record.purchase_order_count = len(tickets.ids)

    def action_view_purchase_orders(self):
        self.ensure_one()
        orders = self.env['purchase.order'].search([
            ('id', 'in', self.sh_purchase_order_ids.ids)
        ])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "purchase.purchase_form_action")
        if len(orders) > 1:
            action['domain'] = [('id', 'in', orders.ids)]
        elif len(orders) == 1:
            form_view = [(self.env.ref('purchase.purchase_order_form').id,
                          'form')]
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


# class HelpdeskTicketPO(models.Model):
#     _inherit = 'sh.helpdesk.ticket'

#     sh_purchase_order_ids = fields.Many2many("purchase.order",
#                                              string="Purchase Orders")
#     purchase_order_count = fields.Integer(
#         'Purchase Order', compute='_compute_purchase_order_count_helpdesk')

#     def action_create_purchase_order(self):
#         context = {'date_planned': fields.Datetime.now()}
#         if self.partner_id:
#             context.update({
#                 'default_partner_id': self.partner_id.id,
#             })
#         if self.user_id:
#             context.update({
#                 'default_user_id': self.user_id.id,
#             })
#         if self:
#             context.update({
#                 'default_sh_purchase_ticket_ids': [(6, 0, self.ids)],
#             })
#         if self.product_ids:
#             line_list = []
#             for product in self.product_ids:
#                 line_vals = {
#                     'product_id': product.id,
#                     'name': product.name_get()[0][1],
#                     'product_qty': 1.0,
#                     'price_unit': product.standard_price,
#                     'product_uom': product.uom_id.id,
#                     'date_planned': fields.Datetime.now()
#                 }
#                 if product.taxes_id:
#                     line_vals.update(
#                         {'taxes_id': [(6, 0, product.supplier_taxes_id.ids)]})
#                 line_list.append((0, 0, line_vals))
#             context.update({'default_order_line': line_list})
#         return {
#             'name': 'Purchase Order',
#             'type': 'ir.actions.act_window',
#             'res_model': 'purchase.order',
#             'view_mode': 'form',
#             'context': context,
#             'target': 'new'
#         }

#     def _compute_purchase_order_count_helpdesk(self):
#         for record in self:
#             record.purchase_order_count = 0
#             tickets = self.env['purchase.order'].search(
#                 [('id', 'in', record.sh_purchase_order_ids.ids)], limit=None)
#             record.purchase_order_count = len(tickets.ids)

#     def action_view_purchase_orders(self):
#         self.ensure_one()
#         orders = self.env['purchase.order'].search([
#             ('id', 'in', self.sh_purchase_order_ids.ids)
#         ])
#         action = self.env["ir.actions.actions"]._for_xml_id(
#             "purchase.purchase_form_action")
#         if len(orders) > 1:
#             action['domain'] = [('id', 'in', orders.ids)]
#         elif len(orders) == 1:
#             form_view = [(self.env.ref('purchase.purchase_order_form').id,
#                           'form')]
#             if 'views' in action:
#                 action['views'] = form_view + \
#                     [(state, view)
#                      for state, view in action['views'] if view != 'form']
#             else:
#                 action['views'] = form_view
#             action['res_id'] = orders.id
#         else:
#             action = {'type': 'ir.actions.act_window_close'}
#         return action
