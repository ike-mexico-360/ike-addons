# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.


from odoo import models, fields, api
from markupsafe import Markup, escape

class MergeTicketWizard(models.TransientModel):

    _name = "sh.helpdesk.ticket.merge.ticket.wizard"
    _description = "Merge Ticket Wizard"


    @api.model
    def _default_sh_check_multi_user(self):
        return self.env.company.sh_display_multi_user if self.env.company.sh_display_multi_user == True else False

    sh_user_id = fields.Many2one('res.users', string='Assigned User',domain = [('share','=',False)])
    ticket_type = fields.Many2one('sh.helpdesk.ticket.type', string='Ticket Type')
    sh_partner_id = fields.Many2one('res.partner', string='Partner',required=True,readonly=True)
    sh_priority = fields.Many2one('helpdesk.priority', string='Priority')
    sh_ticket_alarm_ids = fields.Many2many('sh.ticket.alarm', string='Ticket Reminder')
    sh_helpdesk_ticket_ids = fields.Many2many('sh.helpdesk.ticket', string='Tickets',readonly=True)
    sh_team_id = fields.Many2one('sh.helpdesk.team', string='Team')
    sh_user_ids = fields.Many2many('res.users', string='Assign Multi Users')
    sh_team_head_id = fields.Many2one('res.users', string='Team Head',readonly=True)
    sh_subject_id = fields.Many2one('helpdesk.sub.type', string='Subject')
    sh_helpdesk_tags = fields.Many2many('helpdesk.tags', string='Tags')
    sh_merge_history = fields.Boolean('Merge History',default=False)    
    sh_select_type = fields.Selection([('new', 'New'), ('existing', 'Existing')],string="Type",default="new",required=True)
    sh_existing_ticket= fields.Many2one('sh.helpdesk.ticket',string="Select Ticket")
    sh_check_multi_user = fields.Boolean('sh_check_multi_user',default=_default_sh_check_multi_user)
    
    sh_select_merge_type = fields.Selection(
        string='Merge Type',
        selection=[
            ('close', 'Close other Tickets'),
            ('cancel', 'Cancel other Tickets'),
            ('done', 'Done other Tickets'),
            ('remove', 'Remove other Tickets'),
            ('do_nothing', 'Do Nothing'),
        ],default="do_nothing"
    )
    

    @api.onchange('sh_team_id')
    def _onchange_sh_team_id(self):
            self.sh_team_head_id=self.sh_team_id.team_head.id if self.sh_team_id else False

    def action_merge_tickets(self):
        
        if self.sh_select_type=='new':

            merged_ticket = self.env['sh.helpdesk.ticket'].create({
                'partner_id':self.sh_partner_id.id,
                'ticket_type':self.ticket_type.id if self.ticket_type else False, 
                'priority':self.sh_priority.id if self.sh_priority else False,
                'sh_ticket_alarm_ids':[(6,0,self.sh_ticket_alarm_ids.ids)] if self.sh_ticket_alarm_ids else False,
                'user_id':self.sh_user_id.id if self.sh_user_id else False,
                'team_id':self.sh_team_id.id if self.sh_team_id else False,
                'team_head':self.sh_team_head_id.id if self.sh_team_head_id else False,
                'sh_user_ids': [(6,0,self.sh_user_ids.ids)] if self.sh_user_ids.ids else [],
                'subject_id':self.sh_subject_id.id if self.sh_subject_id else False,
                'tag_ids':[(6,0,self.sh_helpdesk_tags.ids)] if self.sh_helpdesk_tags else []
                })
        else:
            merged_ticket = self.sh_existing_ticket
        
        sorted_tickets = self.sh_helpdesk_ticket_ids.sorted(key=lambda i: i.id)
        product_ids_list=[]
        attachment_ids_list = []
        follower_ids = []
        for ticket in sorted_tickets:
            
            merged_ticket.sh_merge_ticket_ids=[(4,ticket.id)]
            
            get_messages = self.env['mail.message'].search([('res_id','=',ticket.id)], order='id')
            
            if get_messages and self.sh_merge_history:
                # MERGE MAIL-MESSAGE
                for rec in get_messages:
                    rec.res_id = merged_ticket.id
                if ticket.product_ids:
                    product_ids_list = product_ids_list + ticket.product_ids.ids

            get_activities = self.env['mail.activity'].search([('res_id','=',ticket.id)])
        
            
            # MERGE ACTIVITIES
            if get_activities and self.sh_merge_history:
                for rec in get_activities:
                    rec.res_id = merged_ticket.id
            
            follower_ids = follower_ids + ticket.message_partner_ids.ids
            
            attachment_ids_list = attachment_ids_list + ticket.attachment_ids.ids if ticket.attachment_ids else []

        
        # MERGE PRODUCTS
        merged_ticket.product_ids =  [(6,0,product_ids_list)]      
        
        
        # MERGE ATTACHMENT
        merged_ticket.attachment_ids =  [(6,0,attachment_ids_list)]
        # MERGE FOLLOWERS
        merged_ticket.message_subscribe(partner_ids = follower_ids)
        
        # Trigger Onchanges
        merged_ticket.onchange_partner_id()
        # merged_ticket._onchange_sh_helpdesk_policy_ids()
        merged_ticket.onchange_team()
        # merged_ticket.onchange_category()

        marged_disc=""
        merged_ticket.description = False
        for ticket in self.sh_helpdesk_ticket_ids:
            if ticket.description:
                marged_disc = marged_disc + ticket.name + escape(Markup("<hr/>")) + ticket.description + escape(Markup("<br/>")) if not ticket.description == '<p><br></p>' else False
            
            if self.sh_select_merge_type == 'close':
                ticket.stage_id = self.env.company.close_stage_id.id if self.env.company.close_stage_id else False 
            if self.sh_select_merge_type == 'cancel':
                ticket.stage_id = self.env.company.cancel_stage_id.id if self.env.company.close_stage_id else False 
            if self.sh_select_merge_type == 'done':
                ticket.stage_id = self.env.company.done_stage_id.id if self.env.company.close_stage_id else False
            
            
            if self.sh_existing_ticket and ticket.id == self.sh_existing_ticket.id:
                pass
            else:
                ticket.unlink() if self.sh_select_merge_type == 'remove' else False
        merged_ticket.description = marged_disc
