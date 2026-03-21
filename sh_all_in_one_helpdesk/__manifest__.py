# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
{
    "name": "All In One Helpdesk | CRM Helpdesk | Sale Order Helpdesk | Purchase Helpdesk | Invoice Helpdesk | Helpdesk Timesheet | Helpdesk Support Ticket To Task",
    "author": "Softhealer Technologies",
    "website": "https://www.softhealer.com",
    "support": "support@softhealer.com",
    "category": "Discuss",
    "license": "OPL-1",
    "summary": "Flexible HelpDesk Customizable Help Desk Service Desk HelpDesk With Stages Help Desk Ticket Management Helpdesk Email Templates Email Alias Email Helpdesk Chatter Sale Order With Helpdesk,Purchase Order With Helpdesk Invoice With Helpdesk Apps for purchase Material Requisitions Request  purchase product Requisitions Request Material Requisition for tender Material Requisition for manufacturing order Product Request on RFQ Product Request on Tender Product Request on manufacturing order Helpdesk Whatsapp Custom Stages Helpdesk CRM Timesheet Helpdesk  Ticket Tracking Helpdesk Document Helpdesk Solution Helpdesk Multi User Helpdesk Due reminder Helpdesk Sub Ticket Helpdesk Ticket Merge Helpdesk Tickets  Helpdesk Stage Change History Helpdesk Mass Assign Tickets Helpdesk Mass Update Tickets Helpdesk Mass Update tags Helpdesk User Notification Helpdesk Whatsapp Integration Whatsapp Helpdesk Integration Helpdesk Ticket from website customer helpdesk customer helpdesk support ticket online ticketing system for customer support customer supporting Ticketing support Issue Tracking System Website ticket service manage Manage Repair Order With Helpdesk create ticket from the repair order create repair order from thw helpdesk ticket repair oder helpdesk repair order helpdesk create repair order from helpdesk create helpdesk ticket from repair order Automate customer follow-ups Automatic follow-up for leads Automated sales reminders Follow-up workflow automation Automatic task reminders Auto follow-up emails for clients Schedule follow-up notifications Auto follow-up for pending tasks Timely follow-up automation Automate customer followups Automatic followup for leads Automated sales reminders Followup workflow automation Automatic task reminders Auto followup emails for clients Schedule followup notifications Auto followup for pending tasks Timely followup automation Odoo",
    "description": """Are you looking for fully flexible and customisable helpdesk in odoo? Our this apps almost contain everything you need for Service Desk, Technical Support Team, Issue Ticket System which include service request to be managed in Odoo backend. Support ticket will send by email to customer and admin. Customer can view their ticket from the website portal and easily see stage of the reported ticket. This desk is fully customizable clean and flexible. """,
    "version": "18.0.22.0.1",
    "depends": ["mail", "portal", "product", "resource", "sale_management", "purchase", "account", "hr_timesheet", "crm", "project", "repair"],
    "data": [
        "security/sh_helpdesk_security.xml",
        "security/ir.model.access.csv",

        "data/sh_helpdesk_email_data.xml",
        "data/sh_helpdesk_data.xml",
        "data/sh_helpdesk_cron_data.xml",
        "data/sh_helpdesk_stage_data.xml",

        "views/sh_user_push_notification_views.xml",

        "views/sh_helpdesk_menu.xml",
        "views/sh_helpdesk_sla_policies.xml",
        "views/sh_helpdesk_alarm.xml",

        "data/sh_helpdesk_reminder_cron.xml",
        "data/sh_helpdesk_reminder_mail_template.xml",

        "views/sh_helpdesk_team_view.xml",
        "views/sh_helpdesk_ticket_type_view.xml",
        "views/sh_helpdesk_subject_type_view.xml",
        "views/sh_helpdesk_tags_view.xml",
        "views/sh_helpdesk_stages_view.xml",
        "views/sh_helpdesk_category_view.xml",
        "views/sh_helpdesk_subcategory_view.xml",
        "views/sh_helpdesk_priority_view.xml",
        "views/sh_helpdesk_config_settings_view.xml",
        "views/sh_helpdesk_ticket_view.xml",
        "views/sh_report_helpdesk_ticket_template.xml",
        "views/sh_helpdeks_report_portal.xml",
        "views/action_report_views.xml",
        "views/sh_ticket_feedback_template.xml",
        "views/res_users.xml",
        "views/sh_helpdesk_merge_ticket_action.xml",
        "views/sh_helpdesk_ticket_multi_action_view.xml",
        "views/sh_helpdesk_ticket_update_wizard_view.xml",
        "views/sh_helpdesk_ticket_portal_template.xml",
        "views/sh_helpdesk_ticket_megre_wizard_view.xml",
        "views/sh_helpdesk_ticket_task_info.xml",
        "views/sh_customer_hour_package_views.xml",
        "views/res_partner_views.xml",
        "views/sh_ticket_followup_configuration_views.xml",

        "wizard/mail_compose_view.xml",

        "sh_helpdesk_so/security/sh_helpdesk_so_security.xml",
        "sh_helpdesk_so/views/sh_helpdesk_so_tickets.xml",

        "sh_helpdesk_po/security/sh_helpdesk_po_security.xml",
        "sh_helpdesk_po/views/sh_helpdesk_po_tickets.xml",

        "sh_helpdesk_invoice/security/sh_helpdesk_invoice_security.xml",
        "sh_helpdesk_invoice/views/sh_helpdesk_invoice_tickets.xml",

        "sh_helpdesk_timesheet/security/helpdesk_timesheet_security.xml",
        "sh_helpdesk_timesheet/security/ir.model.access.csv",
        "sh_helpdesk_timesheet/views/res_config_setting.xml",
        "sh_helpdesk_timesheet/views/hr_timesheet.xml",
        "sh_helpdesk_timesheet/views/sh_helpdesk_ticket.xml",

        "sh_helpdesk_crm/security/sh_helpdesk_crm_security.xml",
        "sh_helpdesk_crm/views/sh_helpdesk_crm_tickets.xml",

        'sh_helpdesk_task/security/helpdesk_task_security.xml',
        'sh_helpdesk_task/views/sh_helpdesk_ticket.xml',
        'sh_helpdesk_task/views/task.xml',

        "sh_helpdesk_ticket_custom_fields/data/sh_helpdesk_ticket_custom_field_group.xml",
        "sh_helpdesk_ticket_custom_fields/security/ir.model.access.csv",
        "sh_helpdesk_ticket_custom_fields/views/sh_custom_model_helpdesk_ticket_views.xml",
        "sh_helpdesk_ticket_custom_fields/views/sh_custom_model_helpdesk_ticket_tab_views.xml",

        "sh_helpdesk_repair/security/sh_helpdesk_repair_security.xml",
        "sh_helpdesk_repair/views/sh_helpdesk_repair_tickets.xml",
    ],
    'assets': {
         'web.assets_backend': [
            'sh_all_in_one_helpdesk/static/src/js/bus_notifications.js',
             'sh_all_in_one_helpdesk/static/src/js/time_track.js',
            'sh_all_in_one_helpdesk/static/src/xml/TaskTimeCounter.xml',

            'sh_all_in_one_helpdesk/static/src/xml/ticket_main_dashboard_view.xml',
            'sh_all_in_one_helpdesk/static/src/xml/ticket_dashboard_card_view.xml',
            'sh_all_in_one_helpdesk/static/src/xml/ticket_dashboard_tables_dashboard.xml',
            'sh_all_in_one_helpdesk/static/src/js/dashboard_components/ticket_cards_dashboard.js',
            'sh_all_in_one_helpdesk/static/src/js/dashboard_components/ticket_dashboard_tables_dashboard.js',
            'sh_all_in_one_helpdesk/static/src/js/dashboard_components/ticket_main_dashboard.js',
            'sh_all_in_one_helpdesk/static/src/css/ticket_dashboard.css',

            # Systray Notifications
            'sh_all_in_one_helpdesk/static/src/xml/systray_notification_view.xml',
            'sh_all_in_one_helpdesk/static/src/css/notification.scss',
            'sh_all_in_one_helpdesk/static/src/js/systray_notification.js',

            # Bold Ticket
            'sh_all_in_one_helpdesk/static/src/js/views/form_view.js',
            'sh_all_in_one_helpdesk/static/src/js/views/list_view.js',

            # List View Ticket Widget
            'sh_all_in_one_helpdesk/static/src/js/ticket_list_view_widget/ticket_popover_widget.js',
            'sh_all_in_one_helpdesk/static/src/js/ticket_list_view_widget/ticket_popover_widget.xml',

        ],
        'web.assets_frontend': [
            'sh_all_in_one_helpdesk/static/src/js/portal.js',
            'sh_all_in_one_helpdesk/static/src/css/feedback.scss'
        ],
    },
    "application":
    True,
    "auto_install":
    False,
    "installable":
    True,
    'images': [
        'static/description/background.gif',
    ],
    "price":
    107.87,
    "currency":
    "EUR"
}
