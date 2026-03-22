# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class Task(models.Model):
    _inherit = 'project.task'

    ticket_count = fields.Integer('Tickets', compute='_compute_ticket_count')
    sh_ticket_ids = fields.Many2many('sh.helpdesk.ticket', string='Ticket')

    def _compute_ticket_count(self):
        if self:
            for rec in self:
                rec.ticket_count = 0
                ticket_ids = self.env['sh.helpdesk.ticket'].search(
                    [('task_ids', 'in', [rec.id])])
                if ticket_ids:
                    rec.ticket_count = len(ticket_ids.ids)

    def action_view_ticket(self):
        ticket_ids = self.env['sh.helpdesk.ticket'].search(
            [('task_ids', 'in', [self.id])])
        return{
            'name': 'Helpdesk Tickets',
            'res_model': 'sh.helpdesk.ticket',
            'view_mode': 'kanban,list,form',
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', ticket_ids.ids)],
            'target': 'current',
        }

    @api.model_create_multi
    def create(self, vals):
        res = super(Task, self).create(vals)
        if self.env.context.get('active_model') == 'sh.helpdesk.ticket' and self.env.context.get('active_id'):
            res.sh_ticket_ids = [(4,self.env.context.get('active_id'))]
        if res.sh_ticket_ids:
            for ticket in res.sh_ticket_ids:
                ticket.write({
                    'task_ids': [(4, res.id)]
                })
                if ticket.attachment_ids:
                    for attachment in ticket.attachment_ids:
                        self.env['ir.attachment'].create({
                            'name': attachment.name,
                            'type': attachment.type,
                            'datas': attachment.datas,
                            'mimetype': attachment.mimetype,
                            'res_model': 'project.task',
                            'res_id': res.id,
                        })
        return res
