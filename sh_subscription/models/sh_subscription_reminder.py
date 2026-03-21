# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api

class SubscriptionReminder(models.Model):
    _name = "sh.reminder.template"
    _description = "Subscription Reminder"

    name = fields.Char(string="Name", readonly=True)
    sh_reminder = fields.Integer(string="Reminder")
    sh_reminder_unit = fields.Selection(
        [('days(s)', 'Day(s)'), ('week(s)', 'Week(s)'), ('month(s)', 'Month(s)')], 
        string="Reminder Unit", 
        default='days(s)', 
        required=True
    )
    company_id = fields.Many2one(
        'res.company', 
        string='Company', 
        default=lambda self: self.env.company
    )
    sh_mail_template_id = fields.Many2one(
        'mail.template', 
        string='Mail Template'
    )

    def name_get(self):
        """Generates display name for each reminder based on its reminder value and unit."""
        self.read(['sh_reminder', 'sh_reminder_unit'])  # Prefetch fields to avoid unnecessary queries
        return [(alarm.id, f"{alarm.sh_reminder} {alarm.sh_reminder_unit}") for alarm in self]

    @api.onchange('sh_reminder', 'sh_reminder_unit')
    def _onchange_name(self):
        """Updates the 'name' field when 'sh_reminder' or 'sh_reminder_unit' changes."""
        for rec in self:
            try:
                rec.name = rec.name_get()[0][1]  # Extracts the name from the name_get method
            except IndexError:
                rec.name = ''  # Fallback in case name_get returns an empty list

    def safe_browse(self, ids):
        """Handles singleton errors gracefully during record browsing."""
        for attempt in range(3):  # Try three times before failing
            try:
                return self.browse(ids)
            except ValueError:  # Catch singleton error or any other browsing-related error
                if attempt == 2:
                    raise  # Re-raise the error after the last attempt
