# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class HelpdeskCrmTickets(models.Model):
    _inherit = 'crm.lead'

    sh_ticket_ids = fields.Many2many(
        "sh.helpdesk.ticket", string="Tickets")
    ticket_count = fields.Integer(
        'Ticket', compute='_compute_ticket_count')

    def action_create_ticket(self):
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
                'default_sh_lead_ids':  [(6, 0, self.ids)],
            })
        return{
            'name': 'Helpdesk Ticket',
            'type': 'ir.actions.act_window',
            'res_model': 'sh.helpdesk.ticket',
            'view_mode': 'form',
            'context': context,
            'target': 'new'
        }

    def _compute_ticket_count(self):
        for record in self:
            record.ticket_count = 0
            tickets = self.env['sh.helpdesk.ticket'].search(
                [('sh_lead_ids', 'in', record.ids)], limit=None)
            record.ticket_count = len(tickets.ids)

    def ticket_counts(self):
        self.ensure_one()
        tickets = self.env['sh.helpdesk.ticket'].search(
            [('sh_lead_ids', 'in', self.ids)])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sh_all_in_one_helpdesk.sh_helpdesk_ticket_action")
        if len(tickets) > 1:
            action['domain'] = [('id', 'in', tickets.ids)]
        elif len(tickets) == 1:
            form_view = [
                (self.env.ref('sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view').id, 'form')]
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
