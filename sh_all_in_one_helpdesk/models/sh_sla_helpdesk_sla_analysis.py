# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import models, fields, api, _
import math


class HelpdeskSlaAnalysis(models.Model):
    _name = "sh.helpdesk.sla.analysis"
    _description = "Helpdesk SLA Analysis"
    _rec_name = 'sh_sla_id'

    sh_sla_status_id = fields.Many2one(
        string='SLA Status', comodel_name='sh.helpdesk.sla.status')

    sh_sla_status_deadline = fields.Datetime('Deadline')

    sh_sla_status_reached = fields.Datetime('Reached')

    sh_helpdesk_ticket_id = fields.Many2one(
        'sh.helpdesk.ticket', string='Ticket')

    sh_reached_duration = fields.Float('Reached Duration')

    sh_late_duration = fields.Float('Late Duration')

    sh_sla_id = fields.Many2one('sh.helpdesk.sla', string="SLA")

    sh_ticket_stage_id = fields.Many2one(
        'helpdesk.stages', string='Ticket Stage')


class HelpdeskSLAStatus(models.Model):
    _name = 'sh.helpdesk.sla.status'
    _description = "Helpdesk Ticket SLA Status"
    _table = 'sh_helpdesk_sla_status'
    _order = 'id ASC'
    _rec_name = 'sh_sla_id'

    sh_ticket_id = fields.Many2one('sh.helpdesk.ticket',
                                   string='Ticket',
                                   ondelete='cascade',
                                   index=True)
    sh_sla_id = fields.Many2one('sh.helpdesk.sla',
                                required=True,
                                ondelete='cascade')
    sh_sla_stage_id = fields.Many2one('helpdesk.stages',
                                      related='sh_sla_id.sh_stage_id',
                                      store=True)
    sh_deadline = fields.Datetime("SLA Deadline",
                                  compute='_calculate_deadline',
                                  compute_sudo=True,
                                  store=True)
    sh_status = fields.Selection([('sla_failed', 'Failed'),
                                  ('sla_passed', 'Passed'),
                                  ('sh_partially_passed', 'Partially Passed')],
                                 string="Status")
    color = fields.Integer("Color Index", compute='_compute_sh_color')
    sh_done_sla_date = fields.Datetime('SLA Done Date')

    sh_exceeded_hours = fields.Float("Exceeded Hours")

    sh_create_date = fields.Datetime(
        string='Create Date', default=fields.Datetime.now)


    @api.onchange('sh_deadline','sh_done_sla_date')
    def _onchange_compute_status(self):
        for status in self:
            if status.sh_done_sla_date and status.sh_status:
                status.sh_status = 'sla_passed' if status.sh_done_sla_date < status.sh_deadline else 'sla_failed'
            else:
                status.sh_status = 'sh_partially_passed' if not status.sh_deadline or status.sh_deadline > fields.Datetime.now() else 'sla_failed'

    @api.depends('create_date', 'sh_sla_id', 'sh_ticket_id.stage_id')
    def _calculate_deadline(self):
        # SLA Related Code
        for record in self:
            if not record.sh_ticket_id:
                continue

            if record.sh_deadline or record.sh_status == 'failed':
                continue

            # Get the creation date of the associated ticket
            sh_deadline = record.create_date

            # Get the working calendar for the team associated with the ticket
            working_calendar = record.sh_ticket_id.team_id.sh_resource_calendar_id

            if not working_calendar:
                record.sh_deadline = sh_deadline
                record._onchange_compute_status()

            # Calculate the average working hours per day (default to 8 hours per day)
            avg_work_hours = working_calendar.hours_per_day or 8

            # Convert days to hours (1 day = 24 hours)
            day_in_hours = record.sh_sla_id.sh_days * 24

            # Convert minutes to hours (1 minute = 1/60 hour)
            minutes_in_hours = record.sh_sla_id.sh_minutes / 60

            # Add up all the hours
            total_hours = day_in_hours + record.sh_sla_id.sh_hours + minutes_in_hours
            # Calculate the number of working days required to meet the SLA time
            # days_required = math.floor(hours / avg_work_hours)
            days_required = math.floor(total_hours / avg_work_hours)

            if days_required > 0:
                # Plan the sh_deadline date by adding the working days
                sh_deadline = working_calendar.plan_days(days_required + 1, sh_deadline, compute_leaves=True)
                
                create_time = working_calendar.plan_hours(
                    0, record.create_date)

                # Adjust the sh_deadline time to match the creation date time
                sh_deadline = sh_deadline and sh_deadline.replace(hour=create_time.hour, minute=create_time.minute, second=create_time.second, microsecond=create_time.microsecond)

            # Calculate the remaining hours after deducting full working days
            # remaining_hours = record.sh_sla_id.time % avg_work_hours
            remaining_hours = total_hours % avg_work_hours

            # Calculate the sh_deadline for working hours
            deadline_for_work_hours = working_calendar.plan_hours(0, sh_deadline)

            # If the sh_deadline crosses into the next day, reset the time portion
            if deadline_for_work_hours and sh_deadline.day < deadline_for_work_hours.day and days_required > 0:
                sh_deadline = sh_deadline.replace(hour=0, minute=0, second=0, microsecond=0)

            # Set the calculated sh_deadline for the record
            record.sh_deadline = sh_deadline and working_calendar.plan_hours(remaining_hours, sh_deadline, compute_leaves=True)
            record._onchange_compute_status()

    @api.depends('sh_status')
    def _compute_sh_color(self):
        for rec in self:
            rec.color = 4
            if rec.sh_status == 'sla_failed':
                rec.color = 1
            elif rec.sh_status == 'sla_passed':
                rec.color = 10
            elif rec.sh_status == 'sh_partially_passed':
                rec.color = 4
            else:
                rec.color = 0

    def write(self, vals):
        result = super(HelpdeskSLAStatus, self).write(vals)
        for rec in self:
            if vals.get('sh_status') == False and not rec.sh_create_date:
                rec.sh_create_date = fields.Datetime.now()
        return result


class ShHelpdeskTicket(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    sh_sla_deadline = fields.Datetime(
        'SLA Deadline', compute='_compute_sh_sla_deadline', store=True)

    @api.depends('sh_sla_status_ids.sh_deadline')
    def _compute_sh_sla_deadline(self):
        for rec in self:
            sh_deadline = False
            status_ids = rec.sh_sla_status_ids.filtered(
                lambda x: not x.sh_status)
            rec.sh_sla_deadline = min(status_ids.mapped('sh_deadline')) if status_ids else sh_deadline
