# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class HelpdeskTicketType(models.Model):
    _name = 'sh.helpdesk.ticket.type'
    _description = 'Helpdesk Ticket Type'
    _rec_name = 'name'

    name = fields.Char('Name', required=True,translate=True)
    sla_count = fields.Integer(compute='_compute_helpdesk_sla')

    #Ticket Auto Followup start
    sh_followup = fields.Boolean('Follow-up?')
    sh_followup_interval = fields.Integer('Follow-up Interval ')
    sh_followup_inverval_selection = fields.Selection([
        ('days','Days'),
        ('weeks','Weeks'),
        ('months','Months'),
        ('year','Years')
    ],string="Follow-up Interval",default='days')
    sh_number_of_followup = fields.Integer('Number of follow-up')
    sh_followup_template_id = fields.Many2one('mail.template',string='Follow-up Email Template')

    sh_followup_trigger = fields.Boolean('Auto Follow-up trigger?')
    # sh_exclude_stage_ids = fields.Many2many('sh.helpdesk.stages','sh_stage_ticket_type_rel','stage_id','ticket_type_id',string="Exclude Stages")
    sh_followup_config_id = fields.Many2one('sh.ticket.followup.configuration',string='Followup Template')
    #Ticket Auto Followup end

    def _compute_helpdesk_sla(self):
        for record in self:
            record.sla_count = 0
            slas = self.env['sh.helpdesk.ticket'].search(
            [('ticket_type', '=', self.id),('sh_sla_status_ids','!=',False)])
            record.sla_count = len(slas.ids)

    def action_view_sla(self):
        self.ensure_one()
        slas = self.env['sh.helpdesk.ticket'].search(
            [('ticket_type', '=', self.id),('sh_sla_status_ids','!=',False)])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "sh_all_in_one_helpdesk.sh_helpdesk_ticket_action")
        if len(slas) > 1:
            action['domain'] = [('id', 'in', slas.ids)]
        elif len(slas) == 1:
            form_view = [
                (self.env.ref('sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + \
                    [(state, view)
                     for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = slas.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
