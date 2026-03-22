# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models, api
import json

class MassUpdateWizard(models.TransientModel):

    _name = "sh.helpdesk.ticket.mass.update.wizard"
    _description = "Mass Update Wizard"

    helpdesks_ticket_ids = fields.Many2many(comodel_name='sh.helpdesk.ticket')
    check_team_id = fields.Boolean(string='Team ', default=False)
    team_id = fields.Many2one('sh.helpdesk.team', string='Team')
    check_assign_to = fields.Boolean(string='Assign To ', default=False)
    assign_to = fields.Many2one(comodel_name='res.users',
                                string='Assign To',
                                domain=[('share', '=', False)])
    check_sh_display_multi_user = fields.Boolean()
    check_assign_to_multiuser = fields.Boolean(default=False,
                                               string="Assign Multi User")
    ticket_update_type = fields.Selection([
        ('add', 'Add'),
        ('replace', 'Replace'),
    ],
        default="add",
        string="Ticket Type Update ")
    assign_to_multiuser = fields.Many2many('res.users',
                                           string="Assign Multi Users",
                                           domain=[('share', '=', False)])
    sh_user_ids_domain = fields.Char("users domain",compute="_compute_sh_user_ids_domain", store=True)
    check_helpdesks_state = fields.Boolean(default=False, string="Stage")
    helpdesk_stages = fields.Many2one('helpdesk.stages', string="Stages")

    check_add_remove = fields.Boolean(string="Add/Remove", default=False)
    followers = fields.Many2many('res.partner', string="Followers")
    
    ticket_follower_update_type = fields.Selection([
        ('add', 'Add'),
        ('remove', 'Remove'),
    ],
        default="add",
        string="Ticket Type Update")
    
    @api.depends('team_id')
    def _compute_sh_user_ids_domain(self):
        for rec in self:
            domain = [('id', '<', 0)]
            if rec.team_id:
                domain = [('id', 'in', rec.team_id.team_members.ids)]
            rec.sh_user_ids_domain = json.dumps(domain)

    def update_record(self):

        # TEAM UPDATE
        for ticket in self:
   

            if ticket.check_team_id:
                ticket.helpdesks_ticket_ids.write({'team_id': ticket.team_id.id,
                                                'team_head':ticket.team_id.team_head})
                
                
            # <-- ASSIGN TO UPDATE -->
                
            if ticket.check_assign_to:
                ticket.helpdesks_ticket_ids.write({'user_id': ticket.assign_to.id})



            # <-- ASSIGN MULTIUSER UPDATE -->

            if ticket.check_assign_to_multiuser:

                if ticket.ticket_update_type == 'add':
                    get_list = []
                    for rec in ticket.helpdesks_ticket_ids.sh_user_ids:
                        if rec:
                            get_list.append(rec.id)
                    for rec1 in ticket.assign_to_multiuser:
                        if rec1:
                            get_list.append(rec1.id)
                    ticket.helpdesks_ticket_ids.write(
                        {'sh_user_ids': [(6, 0, get_list)]})

                if ticket.ticket_update_type == "replace":
                    ticket.helpdesks_ticket_ids.write(
                        {'sh_user_ids': [(6, 0, ticket.assign_to_multiuser.ids)]})
                    

            # <-- STATE UPDATE -->

            if ticket.check_helpdesks_state:
                for rec in ticket.helpdesks_ticket_ids:
                    if ticket.helpdesk_stages:
                        rec.stage_id = ticket.helpdesk_stages.id


            # <-- ADD/REMOVE FOLLOWER UPDATE -->

            for rec in ticket.helpdesks_ticket_ids:
                ids_list = []
                if ticket.ticket_follower_update_type == "add":
                    rec.message_subscribe(partner_ids=ticket.followers.ids)
                if ticket.ticket_follower_update_type == "remove":
                    for follower in ticket.followers.ids:
                        if follower in rec.message_partner_ids.ids:
                            ids_list.append(follower)
                            final_list = ids_list
                            rec.message_unsubscribe(partner_ids=final_list)


# # -*- coding: utf-8 -*-
# # Part of Softhealer Technologies.
# from odoo import fields, models, _, api
# from odoo.exceptions import UserError


# class MassUpdateWizard(models.TransientModel):

#     _name = "sh.helpdesk.ticket.mass.update.wizard"
#     _description = "Mass Update Wizard"

#     helpdesks_ticket_ids = fields.Many2many(comodel_name='sh.helpdesk.ticket')
#     check_assign_to = fields.Boolean(string=' Asssign To ', default=False)
#     assign_to = fields.Many2one(comodel_name='res.users',
#                                 string='Assign To',
#                                 domain=[('share', '=', False)])
#     check_sh_display_multi_user = fields.Boolean()
#     check_assign_to_multiuser = fields.Boolean(default=False,
#                                                string="Assign Multi User")
#     ticket_update_type = fields.Selection([
#         ('add', 'Add'),
#         ('replace', 'Replace'),
#     ],
#                                           default="add",
#                                           string=" Ticket Type Update ")
#     assign_to_multiuser = fields.Many2many('res.users',
#                                            string="Assign Multi Users",
#                                            domain=[('share', '=', False)])

#     check_helpdesks_state = fields.Boolean(default=False, string=" Stage ")
#     helpdesk_stages = fields.Many2one('helpdesk.stages', string="Stage")

#     check_add_remove = fields.Boolean(string="Add/Remove", default=False)
#     followers = fields.Many2many('res.partner', string="Followers")

#     ticket_follower_update_type = fields.Selection([
#         ('add', 'Add'),
#         ('remove', 'Remove'),
#     ],
#                                                    default="add",
#                                                    string="Ticket Type Update")

#     def update_record(self):

#         # <-- ASSIGN TO UPDATE -->

#         if self.check_assign_to == True:
#             self.helpdesks_ticket_ids.write({'user_id': self.assign_to.id})

#         # <-- ASSIGN MULTIUSER UPDATE -->

#         if self.check_assign_to_multiuser == True:

#             if self.ticket_update_type == 'add':
#                 get_list = []
#                 for rec in self.helpdesks_ticket_ids.sh_user_ids:
#                     if rec:
#                         get_list.append(rec.id)
#                 for rec1 in self.assign_to_multiuser:
#                     if rec1:
#                         get_list.append(rec1.id)
#                 self.helpdesks_ticket_ids.write(
#                     {'sh_user_ids': [(6, 0, get_list)]})

#             if self.ticket_update_type == "replace":
#                 self.helpdesks_ticket_ids.write(
#                     {'sh_user_ids': [(6, 0, self.assign_to_multiuser.ids)]})

#         # <-- STATE UPDATE -->

#         if self.check_helpdesks_state == True:
#             for rec in self.helpdesks_ticket_ids:
#                 if self.helpdesk_stages:
#                     rec.stage_id = self.helpdesk_stages.id

#         # <-- ADD/REMOVE FOLLOWER UPDATE -->

#         for rec in self.helpdesks_ticket_ids:
#             ids_list = []
#             if self.ticket_follower_update_type == "add":
#                 rec.message_subscribe(partner_ids=self.followers.ids)
#             if self.ticket_follower_update_type == "remove":
#                 for follower in self.followers.ids:
#                     if follower in rec.message_partner_ids.ids:
#                         ids_list.append(follower)
#                         final_list = ids_list
#                         rec.message_unsubscribe(partner_ids=final_list)