# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import models, fields, api
from datetime import date


class Timesheet(models.Model):
    _inherit = 'account.analytic.line'

    ticket_id = fields.Many2one('sh.helpdesk.ticket', string='Helpdesk Ticket')
    start_date = fields.Datetime("Start Date")
    end_date = fields.Datetime("End Date")
    sh_customer_hour_package_id = fields.Many2one('sh.customer.hour.package', string='Customer Hour Package')

    domain_str = fields.Char(string="Domain String", compute="_compute_domain_str")

    @api.depends("ticket_id")
    def _compute_domain_str(self):
        for rec in self:
            partner_id = rec.ticket_id.partner_id.id
            today = date.today()
            today_month = today.month
            packages = self.env["sh.customer.hour.package"].search([
                ("partner_id", "=", partner_id),
            ])

            # Filter by month
            package_ids = packages.filtered(
                lambda p: p.sh_package_date and p.sh_package_date.month == today_month
            ).ids

            domain = [("id", "in", package_ids)]
            rec.domain_str = str(domain)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        ticket_id = self.env['sh.helpdesk.ticket'].browse(active_id)
        if ticket_id:

            # For Update Package
            start_date=res.get('date')
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
        return res

    def _get_duration(self, start_date, end_date):
        """ Get the duration value between the 2 given dates. """
        if end_date and start_date:
            diff = fields.Datetime.from_string(
                end_date) - fields.Datetime.from_string(start_date)
            if diff:
                unit_amount = float(diff.days) * 24 + \
                    (float(diff.seconds) / 3600)

                return round(unit_amount, 2)
            return 0.0

    @api.onchange('start_date', 'end_date')
    def onchange_duration_custom(self):
        if self and self.start_date and self.end_date:
            start_date = self.start_date
            date = start_date.date()
            self.date = date
            self.unit_amount = self._get_duration(
                self.start_date, self.end_date)
