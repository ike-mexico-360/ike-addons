
# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import models,fields,api
from datetime import timedelta

class ShHelpdeskTicketCrons(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    @api.model
    def _run_auto_close_ticket(self):
        # Get all companies
        company_ids = self.env['res.company'].search([])

        # Iterate over companies
        for company in company_ids:
            # Check if auto close is enabled for the company
            if company.auto_close_ticket:
                # Find tickets that are not in specific stages
                ticket_ids = self.env['sh.helpdesk.ticket'].search([
                    ('company_id', '=', company.id),
                    ('stage_id', 'not in', [company.done_stage_id.id, company.cancel_stage_id.id, company.close_stage_id.id]),
                ])

                # Iterate over found tickets
                for ticket in ticket_ids:
                    replied_date = ticket.replied_date

                    # Check if there is a replied date and auto close is enabled
                    if replied_date and ticket.company_id.auto_close_ticket:
                        no_of_days = ticket.company_id.close_days
                        end_date = replied_date + timedelta(days=no_of_days)

                        # Check if the end date has passed and the ticket state is 'staff_replied'
                        if end_date < fields.Datetime.now() and ticket.state == 'staff_replied':
                            # Perform the action to close the ticket
                            ticket.action_closed()
