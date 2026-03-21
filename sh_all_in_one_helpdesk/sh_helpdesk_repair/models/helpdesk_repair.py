# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class helpdeskRepair(models.Model):
    _inherit = 'repair.order'

    sh_repair_ticket_ids = fields.Many2many("sh.helpdesk.ticket", string="Tickets")
    repair_ticket_count = fields.Integer('Ticket',
                                       compute='_compute_repair_ticket_count')

    def action_create_repair_ticket(self):
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
                'default_sh_repair_order_ids': [(6, 0, self.ids)],
            })
        if self:
            context.update({
                'default_sh_repair_product_id': self.product_id.id,
            })
        if self.move_ids:
            products = []
            for line in self.move_ids:
                if line.product_id and line.product_id.id not in products:
                    products.append(line.product_id.id)
            context.update({'default_product_ids': [(6, 0, products)]})

        return {
            'name': 'Helpdesk Ticket',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.helpdesk.ticket',
            'view_mode': 'form',
            'context': context,
            'target': 'new'
        }

    def _compute_repair_ticket_count(self):
        for record in self:
            record.repair_ticket_count = 0
            tickets = self.env['sh.helpdesk.ticket'].search(
                [('sh_repair_order_ids', 'in', record.ids)], limit=None)
            record.repair_ticket_count = len(tickets.ids)

    def action_view_repair_tickets(self):
        self.ensure_one()
        tickets = self.env['sh.helpdesk.ticket'].search([
            ('sh_repair_order_ids', 'in', self.ids)
        ])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sh_all_in_one_helpdesk.sh_helpdesk_ticket_action")
        if len(tickets) > 1:
            action['domain'] = [('id', 'in', tickets.ids)]
        elif len(tickets) == 1:
            form_view = [(self.env.ref(
                'sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view').id, 'form')
            ]
            if 'views' in action:
                action['views'] = form_view + \
                    [(state, view)
                     for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = tickets.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
