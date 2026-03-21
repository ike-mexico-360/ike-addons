# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    category = fields.Boolean('Category')
    sub_category = fields.Boolean('Sub Category')
    customer_rating = fields.Boolean('Customer Rating')
    auto_close_ticket = fields.Boolean('Auto Close Ticket')
    close_days = fields.Integer('No of Days')
    new_stage_id = fields.Many2one('helpdesk.stages', string="Draft/New Stage")
    done_stage_id = fields.Many2one('helpdesk.stages', string="Resolved Stage")
    cancel_stage_id = fields.Many2one('helpdesk.stages', string="Cancel Stage")
    allocation_mail_template_id = fields.Many2one(
        'mail.template', string='Ticket Allocation To User Mail Template')
    reply_mail_template_id = fields.Many2one(
        'mail.template', string='Ticket Reply Mail Template')
    dashboard_filter = fields.Many2many('helpdesk.stages',
                                        'rel_company_stage_counter',
                                        string="Dashbaord Filter",
                                        required=True)
    dashboard_tables = fields.Many2many('helpdesk.stages',
                                        'rel_company_stage_tables',
                                        string="Dashbaord Tables",
                                        required=True)
    reopen_stage_id = fields.Many2one('helpdesk.stages',
                                      string="Re-Opened Stage")
    close_stage_id = fields.Many2one('helpdesk.stages', string="Closed Stage")

    enable_manual_add_timesheet = fields.Boolean(string="Manual Add Timesheet")

    sh_default_team_id = fields.Many2one('sh.helpdesk.team',
                                         string="Default Team")
    sh_default_user_id = fields.Many2one('res.users',
                                         string="Default Assign User")
    sh_display_multi_user = fields.Boolean('Display Multi Users ?')
    sh_configure_activate = fields.Boolean('Manage Products')
    sh_display_ticket_reminder = fields.Boolean('Ticket Reminder ?')
    sh_ticket_product_detail = fields.Boolean(
        "Ticket Product details in Message?", default=True)
    sh_signature = fields.Boolean("Signature?", default=True)
    sh_display_in_chatter = fields.Boolean("Display in Chatter Message?",
                                           default=True)
    sh_pdf_in_message = fields.Boolean("Send Report URL in Message?",
                                       default=True)
    sh_ticket_url_in_message = fields.Boolean("Send Ticket URL in Message?",
                                              default=True)
    sh_receive_email_seeing_ticket = fields.Boolean(
        'Get email when customer view ticket ?')
    sh_auto_add_customer_as_follower = fields.Boolean(
        'Auto add customer as follower when create ticket ?', default=True)

    sh_customer_replied = fields.Boolean(
        'Stage change when customer replied ?')

    sh_customer_replied_stage_id = fields.Many2one(
        'helpdesk.stages', string='Customer Replied Stage')

    sh_staff_replied_stage_id = fields.Many2one('helpdesk.stages',
                                                string='Staff Replied Stage')

    sh_staff_replied = fields.Boolean('Stage change when staff replied ?')
    sh_file_size = fields.Integer('Portal Attachment Size(KB)')

    access_for_everyone = fields.Boolean(
        string='Access For Everyone')

    # Send Notification
    sh_send_notification_create = fields.Boolean('Send Notification When Creating Ticket')
    sh_send_notification_assign = fields.Boolean('Send Notification When Ticket is Assigned')
    sh_send_notification_done = fields.Boolean('Send Notification When Ticket is Completed')
    sh_send_notification_cancelled = fields.Boolean('Send Notification When Ticket is Cancelled')

    # For Customer Hour Package
    sh_allocated_hours = fields.Integer('Allocated Hours For Month')

    #For Auto followup
    sh_auto_followup_stage_id = fields.Many2one('helpdesk.stages',string='Auto Followup Stage')

    def write(self, vals):
        res = super().write(vals)
        if 'sh_allocated_hours' in vals:
            new_hours = vals['sh_allocated_hours']
            self.env['res.partner'].sudo().search([]).write({
                'sh_allocated_hours': new_hours
            })

        return res

class HelpdeskSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    access_for_everyone = fields.Boolean(
        string='Portal View Ticket with Access Token',
        related='company_id.access_for_everyone',
        readonly=False
    )

    enable_manual_add_timesheet = fields.Boolean(string="Manual Add Timesheet",related='company_id.enable_manual_add_timesheet',readonly=False)

    company_id = fields.Many2one('res.company',
                                 string='Company',
                                 required=True,
                                 default=lambda self: self.env.company)
    category = fields.Boolean(string='Category',
                              related='company_id.category',
                              readonly=False)
    sub_category = fields.Boolean(string='Sub Category',
                                  related='company_id.sub_category',
                                  readonly=False)
    customer_rating = fields.Boolean(string='Customer Rating',
                                     related='company_id.customer_rating',
                                     readonly=False)
    auto_close_ticket = fields.Boolean(string='Auto Close Ticket',
                                       related='company_id.auto_close_ticket',
                                       readonly=False)
    close_days = fields.Integer(string='No of Days',
                                related='company_id.close_days',
                                readonly=False)
    new_stage_id = fields.Many2one('helpdesk.stages',
                                   string="Draft/New Stage",
                                   related='company_id.new_stage_id',
                                   readonly=False)
    done_stage_id = fields.Many2one('helpdesk.stages',
                                    string="Resolved Stage",
                                    related='company_id.done_stage_id',
                                    readonly=False)
    cancel_stage_id = fields.Many2one('helpdesk.stages',
                                      string="Cancel Stage",
                                      related='company_id.cancel_stage_id',
                                      readonly=False)
    allocation_mail_template_id = fields.Many2one(
        'mail.template',
        string='Ticket Allocation To User Mail Template',
        related='company_id.allocation_mail_template_id',
        readonly=False)
    reply_mail_template_id = fields.Many2one(
        'mail.template',
        string='Ticket Reply Mail Template',
        related='company_id.reply_mail_template_id',
        readonly=False)
    dashboard_filter = fields.Many2many('helpdesk.stages',
                                        'rel_company_stage_counter',
                                        string="Dashbaord Filter",
                                        related="company_id.dashboard_filter",
                                        readonly=False,
                                        required=True)
    dashboard_tables = fields.Many2many('helpdesk.stages',
                                        'rel_company_stage_tables',
                                        string="Dashbaord Tables",
                                        related="company_id.dashboard_tables",
                                        readonly=False,
                                        required=True)
    reopen_stage_id = fields.Many2one('helpdesk.stages',
                                      string="Re-Opened Stage",
                                      readonly=False,
                                      related='company_id.reopen_stage_id')
    close_stage_id = fields.Many2one('helpdesk.stages',
                                     string="Closed Stage",
                                     readonly=False,
                                     related='company_id.close_stage_id')
    sh_default_team_id = fields.Many2one(
        'sh.helpdesk.team',
        string="Default Team",
        readonly=False,
        related='company_id.sh_default_team_id')
    sh_default_user_id = fields.Many2one(
        'res.users',
        string="Default Assign User",
        readonly=False,
        related='company_id.sh_default_user_id')
    sh_display_multi_user = fields.Boolean(
        'Display Multi Users ?',
        related='company_id.sh_display_multi_user',
        readonly=False)
    sh_configure_activate = fields.Boolean(
        'Manage Products',
        related='company_id.sh_configure_activate',
        readonly=False)
    sh_display_ticket_reminder = fields.Boolean(
        'Ticket Reminder ?',
        related='company_id.sh_display_ticket_reminder',
        readonly=False)
    sh_ticket_product_detail = fields.Boolean(
        "Ticket Product details in Message?",
        related='company_id.sh_ticket_product_detail',
        readonly=False)
    sh_signature = fields.Boolean("Signature?",
                                  related='company_id.sh_signature',
                                  readonly=False)
    sh_display_in_chatter = fields.Boolean(
        "Display in Chatter Message?",
        related='company_id.sh_display_in_chatter',
        readonly=False)
    sh_pdf_in_message = fields.Boolean("Send Report URL in Message?",
                                       related='company_id.sh_pdf_in_message',
                                       readonly=False)
    sh_ticket_url_in_message = fields.Boolean(
        "Send Ticket URL in Message?",
        related='company_id.sh_ticket_url_in_message',
        readonly=False)
    sh_receive_email_seeing_ticket = fields.Boolean(
        'Get email when customer view ticket ?',
        related='company_id.sh_receive_email_seeing_ticket',
        readonly=False)
    sh_auto_add_customer_as_follower = fields.Boolean(
        'Auto add customer as follower when create ticket ?',
        related='company_id.sh_auto_add_customer_as_follower',
        readonly=False)

    sh_customer_replied = fields.Boolean(
        'Stage change when customer replied ?',
        related='company_id.sh_customer_replied',
        readonly=False)

    sh_customer_replied_stage_id = fields.Many2one(
        'helpdesk.stages',
        string='Customer Replied Stage',
        related='company_id.sh_customer_replied_stage_id',
        readonly=False)
    sh_staff_replied_stage_id = fields.Many2one(
        'helpdesk.stages',
        string='Staff Replied Stage',
        related='company_id.sh_staff_replied_stage_id',
        readonly=False)

    sh_staff_replied = fields.Boolean('Stage change when staff replied ?',
                                      related='company_id.sh_staff_replied',
                                      readonly=False)
    sh_file_size = fields.Integer('Portal Attachment Size(KB)',related='company_id.sh_file_size',readonly=False)

    # Send Notification
    sh_send_notification_create = fields.Boolean(related='company_id.sh_send_notification_create',readonly=False)
    sh_send_notification_assign = fields.Boolean(related='company_id.sh_send_notification_assign',readonly=False)
    sh_send_notification_done = fields.Boolean(related='company_id.sh_send_notification_done',readonly=False)
    sh_send_notification_cancelled = fields.Boolean(related='company_id.sh_send_notification_cancelled',readonly=False)

    # For Customer Hour Package
    sh_allocated_hours = fields.Integer(related='company_id.sh_allocated_hours',readonly=False)

    #For Auto followup
    sh_auto_followup_stage_id = fields.Many2one('helpdesk.stages',string='Auto Followup Stage',readonly=False,related='company_id.sh_auto_followup_stage_id')


    @api.onchange('sh_default_team_id')
    def onchange_sh_default_team_id(self):
        if self.sh_default_team_id:
            domain = {}
            domain = {
                'sh_default_user_id':
                [('id', 'in', self.sh_default_team_id.team_members.ids)]
            }
            return {'domain': domain}
