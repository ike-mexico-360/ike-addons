# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields

class TicketAutoFollowupConfiguration(models.Model):
    _name = 'sh.ticket.followup.configuration'
    _description = 'Ticket Auto Followup Configuration'

    name = fields.Char('Name',required=True)
    sequence = fields.Integer(string="Sequence",default=10)
    sh_ticket_followup_line_ids = fields.One2many('sh.ticket.followup.configuration.line','sh_followup_id','Followup Configuration lines')

class TicketAutoFollowupConfigurationLine(models.Model):
    _name = 'sh.ticket.followup.configuration.line'
    _description = 'Ticket Auto Followup Configuration lines'

    sh_interval = fields.Integer('Interval',required=True)
    sequence = fields.Integer(string="Sequence",default=10)
    sh_email_template_id = fields.Many2one('mail.template',string='Email Template',domain=[('model','=','sh.helpdesk.ticket')])
    sh_followup_id = fields.Many2one('sh.ticket.followup.configuration',string='Auto Followup Configuration')