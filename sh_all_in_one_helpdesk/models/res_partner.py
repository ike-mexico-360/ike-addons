# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api
from odoo.http import request


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sh_custom_hour_package_line = fields.One2many(comodel_name='sh.customer.hour.package', inverse_name='partner_id', string='Customer Hour Package Line')

    # For Customer Hour Package
    sh_allocated_hours = fields.Integer('Allocated Hours For Month')


    # For smart button
    partner_ticket_count = fields.Integer('Ticket',
                                       compute='_compute_sale_ticket_count')

    def _compute_sale_ticket_count(self):
        for record in self:
            record.partner_ticket_count = 0
            tickets = self.env['sh.helpdesk.ticket'].search(
                [('partner_id', '=', record.id)], limit=None)
            record.partner_ticket_count = len(tickets.ids)

    def action_view_partner_tickets(self):
        self.ensure_one()
        tickets = self.env['sh.helpdesk.ticket'].sudo().search([
            ('partner_id', '=', self.id)
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
