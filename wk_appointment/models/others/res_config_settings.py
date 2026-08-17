from odoo import _, models, fields, api


class ResConfigSettings(models.TransientModel):

    _inherit = 'res.config.settings'

    appointment_wait_time = fields.Integer(
        string="Appointment Scheduling Wait Time",
        default=0,
        config_parameter="wk_appointment.appointment_wait_time",
    )

    events_display_wait_time = fields.Integer(
        string="Scheduled Events Display Wait Time",
        default=0,
        config_parameter="wk_appointment.events_display_wait_time",
    )
