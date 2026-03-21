# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import models, fields, _



class FollowupHistory(models.Model):
    _name = 'sh.followup.history'
    _description = 'Followup History'

    sh_schedule_date = fields.Date('Schedule Date')
    sh_date_of_followup = fields.Date('Date of followup')
    # sh_quick_reply_template_id = fields.Many2one('sh.quick.reply','Quick Reply Template')
    sh_email_template_id = fields.Many2one('mail.template',string='Email Template')
    sh_status = fields.Selection([('pending','Pending'),('failure','Failure'),('success','Success')],string='Status')
    sh_followup_ticket_id = fields.Many2one('sh.helpdesk.ticket',string='Followup Ticket')
    sh_failure_reason = fields.Text('Failure Reason')