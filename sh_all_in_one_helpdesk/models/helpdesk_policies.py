# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields
import logging
_logger = logging.getLogger(__name__)

class HelpdeskSLAPolicies(models.Model):
    _name = 'sh.helpdesk.sla'
    _description = 'Helpdesk SLA Policies'

    def get_deafult_company(self):
        company_id = self.env.company
        return company_id

    name = fields.Char('Name',required=True)
    sh_team_id = fields.Many2one('sh.helpdesk.team','Helpdesk Team',required=True)
    sh_ticket_type_id = fields.Many2one('sh.helpdesk.ticket.type','Ticket Type')
    sh_sla_target_type = fields.Selection([('reaching_stage','Reaching Stage'),('assign_to','Assigned To')],default='reaching_stage',string='SLA Target Type ') # Not Useable from V17
    sh_sla_target_type_selection = fields.Selection([('reaching_stage','Reaching Stage')],default='reaching_stage',string='SLA Target Type') # V17 Onwards
    sh_stage_id = fields.Many2one('helpdesk.stages',string='Reach Stage')
    sh_days = fields.Integer('Days',required=True)
    sh_hours = fields.Integer('Hours',required=True)
    sh_minutes = fields.Integer('Minutes',required=True)
    company_id = fields.Many2one(
        'res.company', string="Company", default=get_deafult_company)

    sla_ticket_count = fields.Integer(compute='_compute_helpdesk_ticket_sla')

    def _compute_helpdesk_ticket_sla(self):
        for record in self:
            record.sla_ticket_count = 0
            tickets = self.env['sh.helpdesk.ticket'].search([('sh_sla_policy_ids', 'in', self.ids)])
            record.sla_ticket_count = len(tickets.ids)

    def action_view_tickets(self):
        self.ensure_one()
        tickets = self.env['sh.helpdesk.ticket'].search(
            [('sh_sla_policy_ids', 'in', self.ids)])
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


class ShHelpdeskSla(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    # sh_sla_policy_ids = fields.Many2many('sh.helpdesk.sla','sh_helpdesk_sla_status','sh_ticket_id','sh_sla_id',string="Helpdesk SLA Policies",copy=False)
    sh_sla_policy_ids = fields.Many2many('sh.helpdesk.sla',string="Helpdesk SLA Policies",copy=False)

    sh_sla_status_ids = fields.One2many('sh.helpdesk.sla.status','sh_ticket_id',string="Helpdesk SLA Status")

    def sh_conclude_sla(self):
        for each_ticket in self:
            existed_sla_in_ticket = each_ticket.sh_sla_status_ids.filtered(lambda each_status:not each_status.sh_done_sla_date)
            for each_sla_status in existed_sla_in_ticket:
                if each_sla_status.sh_sla_id:
                    if each_sla_status.sh_sla_id.sh_stage_id.id == each_ticket.stage_id.id:
                        each_sla_status.write({'sh_done_sla_date': fields.Datetime.now()})
                        each_sla_status._onchange_compute_status()
                        # *******************************************************
                        # Both Stages Are Matched Means its Time to conclude
                        # *******************************************************
                        if each_sla_status.sh_deadline and each_sla_status.sh_ticket_id.team_id.sh_resource_calendar_id:
                            reached_datetime = each_sla_status.sh_done_sla_date or fields.Datetime.now()
                            if reached_datetime <= each_sla_status.sh_deadline:
                                start_dt = reached_datetime
                                end_dt = each_sla_status.sh_deadline
                                factor = -1
                            else:
                                start_dt = each_sla_status.sh_deadline
                                end_dt = reached_datetime
                                factor = 1
                            duration_data = each_sla_status.sh_ticket_id.team_id.sh_resource_calendar_id.get_work_duration_data(start_dt, end_dt, compute_leaves=True)
                            each_sla_status.sh_exceeded_hours = duration_data['hours'] * factor
                        else:
                            each_sla_status.sh_exceeded_hours = False

    def sh_apply_sla(self):
        try:
            for each_ticket in self:
                # Removed SLA Status which is conclude
                get_current_slas = each_ticket.sh_sla_status_ids.filtered(lambda each_status:not each_status.sh_done_sla_date)
                get_current_slas.write({'sh_ticket_id':False})

                policies = self.env['sh.helpdesk.sla'].search([('sh_team_id','=',each_ticket.team_id.id),('sh_ticket_type_id','=',each_ticket.ticket_type.id)])
                if policies:
                    policies = policies.ids
                    # Create New SLA Status
                    for each_policy in policies:
                        self.env['sh.helpdesk.sla.status'].create({'sh_sla_id':each_policy,'sh_ticket_id':each_ticket.id})

        except Exception as e:
            _logger.exception("Error while Applying SLA %s", e)


# class HelpdeskSLAPolicies(models.Model):
#     _name = 'sh.helpdesk.sla'
#     _description = 'Helpdesk SLA Policies'

#     def get_deafult_company(self):
#         company_id = self.env.company
#         return company_id

#     name = fields.Char('Name',required=True)
#     sh_team_id = fields.Many2one('sh.helpdesk.team','Helpdesk Team',required=True)
#     sh_ticket_type_id = fields.Many2one('sh.helpdesk.ticket.type','Helpdesk Team Type')
#     sh_sla_target_type = fields.Selection([('reaching_stage','Reaching Stage'),('assign_to','Assigned To')],default='reaching_stage',string='SLA Target Type')
#     sh_stage_id = fields.Many2one('helpdesk.stages',string='Reach Stage')
#     sh_days = fields.Integer('Days',required=True)
#     sh_hours = fields.Integer('Hours',required=True)
#     sh_minutes = fields.Integer('Minutes',required=True)
#     company_id = fields.Many2one(
#         'res.company', string="Company", default=get_deafult_company)
#     sla_ticket_count = fields.Integer(compute='_compute_sh_helpdesk_ticket_sla')

#     def _compute_sh_helpdesk_ticket_sla(self):
#         for record in self:
#             record.sla_ticket_count = 0
#             tickets = self.env['sh.helpdesk.ticket'].search(
#                 [('sh_sla_policy_ids', 'in', self.ids)], limit=None)
#             record.sla_ticket_count = len(tickets.ids)


#     def action_view_tickets(self):
#         self.ensure_one()
#         tickets = self.env['sh.helpdesk.ticket'].search(
#             [('sh_sla_policy_ids', 'in', self.ids)])
#         action = self.env["ir.actions.actions"]._for_xml_id(
#             "sh_all_in_one_helpdesk.sh_helpdesk_ticket_action")
#         if len(tickets) > 1:
#             action['domain'] = [('id', 'in', tickets.ids)]
#         elif len(tickets) == 1:
#             form_view = [
#                 (self.env.ref('sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view').id, 'form')]
#             if 'views' in action:
#                 action['views'] = form_view + \
#                     [(state, view)
#                      for state, view in action['views'] if view != 'form']
#             else:
#                 action['views'] = form_view
#             action['res_id'] = tickets.id
#         else:
#             action = {'type': 'ir.actions.act_window_close'}
#         return action
