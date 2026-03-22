# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api,_
from datetime import datetime
from odoo.exceptions import UserError


class TicketTimeAccountLine(models.Model):
    _name = 'ticket.time.account.line'
    _description = 'Ticket Time Account Line'

    def _get_default_start_time(self):
        active_model = self.env.context.get('active_model')
        if active_model == 'sh.helpdesk.ticket':
            active_id = self.env.context.get('active_id')
            if active_id:
                ticket_search = self.env['sh.helpdesk.ticket'].search(
                    [('id', '=', active_id)], limit=1)
                return ticket_search.start_time

    def _get_default_end_time(self):
        return datetime.now()

    def _get_default_duration(self):
        active_model = self.env.context.get('active_model')
        if active_model == 'sh.helpdesk.ticket':
            active_id = self.env.context.get('active_id')
            if active_id:
                ticket_search = self.env['sh.helpdesk.ticket'].search(
                    [('id', '=', active_id)], limit=1)
                diff = fields.Datetime.from_string(fields.Datetime.now(
                )) - fields.Datetime.from_string(ticket_search.start_time)
                if diff:
                    duration = float(diff.days) * 24 + \
                        (float(diff.seconds) / 3600)
                    return round(duration, 2)

    name = fields.Char("Description", required=True)
    start_date = fields.Datetime(
        "Start Date", default=_get_default_start_time, readonly=True)
    end_date = fields.Datetime(
        "End Date", default=_get_default_end_time, readonly=True)
    duration = fields.Float(
        "Duration (HH:MM)", default=_get_default_duration, readonly=True)
    # duration = fields.Float(
    #     "Duration (HH:MM)")
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)
    project_id = fields.Many2one('project.project', string='Project')
    sh_customer_hour_package_id = fields.Many2one('sh.customer.hour.package', string='Customer Hour Package')
    sh_helpdesk_ticket_id = fields.Many2one('sh.helpdesk.ticket', string='Ticket')

    @api.model
    def default_get(self, fields_list):
        res = super(TicketTimeAccountLine, self).default_get(fields_list)
        active_id = self.env.context.get('active_id')
        ticket_id = self.env['sh.helpdesk.ticket'].browse(active_id)
        if ticket_id:
            # For Update Package
            start_date=res.get('start_date').date()
            package_id = self.env["sh.customer.hour.package"].search([
                ("partner_id", "=", ticket_id.partner_id.id),
                ("sh_package_date", "<=", start_date),
                ("sh_package_date_end", ">=", start_date),
            ])
            if package_id:
                res.update({
                    'sh_customer_hour_package_id':package_id.id
                })
            # For Update Package
            res.update({
                'sh_helpdesk_ticket_id':ticket_id.id,
            })
            timesheet_line = ticket_id.timehseet_ids.filtered(
                lambda x: x.ticket_id.id == ticket_id.id and x.end_date == False and x.start_date != False)
            if timesheet_line:
                res.update({
                    'project_id': timesheet_line.project_id.id,
                })
        else:
            if self.env.company.project_id:
                res.update({
                    'project_id': self.env.company.project_id.id,
                })
        return res

    def end_ticket(self):
        context = dict(self.env.context or {})
        active_model = context.get('active_model', False)
        active_id = context.get('active_id', False)

        vals = {'name': self.name, 'unit_amount': self.duration,
                'amount': self.duration, 'date': datetime.now()}
        ticket_search = False
        if active_model == 'sh.helpdesk.ticket':
            if active_id:
                ticket_search = self.env['sh.helpdesk.ticket'].search(
                    [('id', '=', active_id)], limit=1)

                package_remaining_hours=self.sh_customer_hour_package_id.sh_remaining_hours_at_month_end
                if package_remaining_hours<self.duration:
                    raise UserError(
                        "You cannot close the ticket because you have exceeded the allocated hours limit.")

                if ticket_search:
                    vals.update({'start_date': ticket_search.start_time})
                    vals.update({'end_date': datetime.now()})
                    vals.update({'ticket_id': ticket_search.id})
                if self.project_id:
                    vals.update({'project_id': self.project_id.id})
                    act_id = self.env['project.project'].browse(
                        self.project_id.id).account_id
                    if act_id:
                        vals.update({'account_id': act_id.id})
                else:
                    vals.update({'project_id': self.env.company.project_id.id})
                    act_id = self.env['project.project'].browse(
                        self.env.company.project_id.id).account_id
                    if act_id:
                        vals.update({'account_id': act_id.id})

                # For Customer Hour Package
                if self.sh_customer_hour_package_id:
                    vals.update({'sh_customer_hour_package_id': self.sh_customer_hour_package_id.id})

        timesheet_line = self.env['account.analytic.line'].search(
            [('ticket_id', '=', ticket_search.id), ('end_date', '=', False),('employee_id.user_id','=',self.env.user.id)], limit=1)
        if timesheet_line:
            timesheet_line.write(vals)
            if ticket_search:
                ticket_search.write({'start_time': False, 'duration': 0.0,'ticket_running':False})
        self._cr.commit()

        self.env.user.write({'sh_running_ticket_id':False})

        return {'type': 'ir.actions.client', 'tag': 'reload'}


class ShHelpdesk(models.Model):
    _name = 'sh.helpdesk.ticket'
    _inherit = ['sh.helpdesk.ticket']

    start_time = fields.Datetime("Start Time", copy=False, compute='_compute_start_time_test')
    end_time = fields.Datetime("End Time", copy=False,compute='_compute_end_time_test')
    total_time = fields.Char("Total Time", copy=False)
    timehseet_ids = fields.One2many(
        'account.analytic.line', 'ticket_id', string='Timesheets')
    duration = fields.Float('Real Duration', compute='_compute_duration')
    ticket_running = fields.Boolean("Ticket Running")
    ticket_run = fields.Boolean("Ticket run", compute='_check_ticket_run')

    # -----------------------------------------------------------------------------
    # COMPUTE END-TIME BASED ON USER SPECIFIC TIMESHEET FROM TIMESHEET MENU
    # -----------------------------------------------------------------------------
    def _compute_end_time_test(self):
        for rec in self:
            rec.end_time = False
            timesheet_ids = self.env['account.analytic.line'].search([('ticket_id','=',rec.id),('end_date','=',False),('start_date','!=',False),('employee_id.user_id','=',self.env.user.id)])
            if timesheet_ids:
                if len(timesheet_ids) > 1: # Get The Latest Record's Start Date
                    rec.end_time = timesheet_ids[1].end_date
                else:
                    rec.end_time = timesheet_ids.end_date
    # -----------------------------------------------------------------------------
    # COMPUTE END-TIME BASED ON USER SPECIFIC TIMESHEET FROM TIMESHEET MENU
    # -----------------------------------------------------------------------------



    # -----------------------------------------------------------------------------
    # COMPUTE START-TIME BASED ON USER SPECIFIC TIMESHEET FROM TIMESHEET MENU
    # -----------------------------------------------------------------------------
    def _compute_start_time_test(self):
        for rec in self:
            timesheet_ids = self.env['account.analytic.line'].search([('ticket_id','=',rec.id),('end_date','=',False),('start_date','!=',False),('employee_id.user_id','=',self.env.user.id)])
            if timesheet_ids:
                if len(timesheet_ids) > 1:
                    rec.start_time = timesheet_ids[1].start_date # Get The Latest Record's Start Date
                else:
                    rec.start_time = timesheet_ids.start_date
            else:
                rec.start_time = False
    # -----------------------------------------------------------------------------
    # COMPUTE START-TIME BASED ON USER SPECIFIC TIMESHEET FROM TIMESHEET MENU
    # -----------------------------------------------------------------------------



    # -----------------------------------------------------------------------------
    # CHECK TRUE/FALSE BASED ON TIMER START BY USER AND RELATED TIMESHEET ENTRY
    # -----------------------------------------------------------------------------
    def _check_ticket_run(self):

        for rec in self:
            rec.ticket_run = False
            if self.env.user.sh_running_ticket_id.id == rec.id:
                rec.ticket_run = True

    # -----------------------------------------------------------------------------
    # CHECK TRUE/FALSE BASED ON TIMER START BY USER AND RELATED TIMESHEET ENTRY
    # -----------------------------------------------------------------------------


    @api.model
    def get_duration(self, ticket):
        if ticket:
            ticket = self.browse(int(ticket))
            if ticket and ticket.start_time:
                diff = fields.Datetime.from_string(
                    fields.Datetime.now()) - fields.Datetime.from_string(ticket.start_time)
                if diff:
                    duration = float(diff.days) * 24 + \
                        (float(diff.seconds) / 3600)
                    return diff.total_seconds() * 1000

    # @api.depends('timehseet_ids.unit_amount')
    def _compute_duration(self):
        for rec in self:
            rec.duration = 0.0
            if rec and rec.timehseet_ids:
                timesheet_line = self.env['account.analytic.line'].search([('id','in',rec.timehseet_ids.ids),('ticket_id','=',rec.id),('end_date','=',False),('start_date','!=',False),('employee_id.user_id','=',self.env.user.id)])
                if timesheet_line:
                    rec.duration = timesheet_line[0].unit_amount

    def action_ticket_start(self):
        # running_ticket=self.env["account.analytic.line"].search([('employee_id.user_id','=',self.env.user.id),('start_date','!=',False),('end_date','=',False)])
        # if self.env.user.sh_running_ticket_id and not self.env.company.sh_multiple_ticket_allowed:
        #     raise UserError(
        #         "You can't start multiple ticket timer at a same time.. !")


        # if running_ticket and not self.env.company.sh_multiple_ticket_allowed:
        #     raise UserError("You can not start 2 tickets at same time !")

        # if not self.env.company.project_id:
        #     raise UserError(
        #         "Please Set Default Project from configuration!")

        # old
        if self.env.user.sh_running_ticket_id:
            raise UserError(
                "You can't start multiple ticket timer at a same time.. !")
        else:
            if not self.env.company.sh_multiple_ticket_allowed:
                timesheet_ids = self.env['account.analytic.line'].search([('ticket_id','=',self.id),('start_date','!=',False),('end_date','=',False),('employee_id.user_id','!=',self.env.user.id)],limit=1)
                if timesheet_ids:
                    raise UserError("Already Another Employee working in same ticket !")
        if not self.env.company.project_id:
            raise UserError(
                "Please Set Default Project from configuration!")

        if not self.env.company.sh_multiple_ticket_allowed:
            timesheet_ids = self.env['account.analytic.line'].search([('ticket_id','=',self.id),('start_date','!=',False),('end_date','=',False),('employee_id.user_id','!=',self.env.user.id)],limit=1)
            if timesheet_ids:
                raise UserError("Already Another Employee working in same ticket !")
        vals = {'name': '/', 'date': datetime.now()}
        if self:
            vals.update({'start_date': datetime.now()})
            vals.update({'ticket_id': self.id})
        usr_id = self.env.user.id
        if usr_id:
            emp_search = self.env['hr.employee'].search(
                [('user_id', '=', usr_id)], limit=1)
            if emp_search:
                vals.update({'employee_id': emp_search.id})
            else:
                raise UserError(_("No employee found for %s") % (self.env.user.name,))
        if self.env.company.project_id:
            vals.update({'project_id': self.env.company.project_id.id})
            act_id = self.env['project.project'].browse(
                self.env.company.project_id.id).account_id
                # self.env.company.project_id.id).analytic_account_id
            if act_id:
                vals.update({'account_id': act_id.id})
        self.env['account.analytic.line'].create(vals)
        self.write({'ticket_running': True})
        self._cr.commit()

        # update for not start multiple ticket

        self.env.user.write({'sh_running_ticket_id':self.id})

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_ticket_end(self):

        # start_time_rec = self.timehseet_ids.filtered(lambda x: x.ticket_id.id == self.id and x.end_date == False and x.start_date != False and x.employee_id.user_id == self.env.user)

        if self.env.company.sh_default_description:
            context = {}
            context.update({
                'default_name': str(self.env.user.name)+'-'+str(self.name)
            })
            return {
                'name': "End Ticket",
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'ticket.time.account.line',
                'context': context,
                'target': 'new',
            }
        else:
            return {
                'name': "End Ticket",
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'ticket.time.account.line',
                'target': 'new',
            }
