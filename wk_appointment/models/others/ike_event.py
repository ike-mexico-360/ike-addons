from odoo import models, fields, api, _
from datetime import timedelta
import logging


class IkeEvent(models.Model):
    _inherit = 'ike.event'

    appointment_type = fields.Boolean(
        string="Schedule",
        default=False,
    )
    appointment_wait_time = fields.Integer(
        readonly=True,
        copy=False,
    )
    appointment_min_date = fields.Datetime(
        string='Min event date',
        readonly=True,
    )

    # events_display_wait_time = fields.Integer(
    #     readonly=True,
    #     copy=False,
    # )
    # appointment_show_event_date = fields.Datetime(
    #     string="Display event date"
    # )

    # ==== FUNCTION ==== #
    def _get_appointment_wait_time(self):
        return int(
            self.env['ir.config_parameter'].sudo().get_param(
                'wk_appointment.appointment_wait_time',
                default=0,
            )
        )

    # def _get_appointment_wait_to_show_event(self):
    #     return int(
    #         self.env['ir.config_parameter'].sudo().get_param(
    #             'wk_appointment.events_display_wait_time',
    #             default=0,
    #         )
    #     )

    # ==== ONCHANGE ==== #
    @api.onchange('appointment_type')
    def onchange_event_date(self):
        if self.appointment_type:
            self.event_date = self.appointment_min_date

    # ==== CRUD ==== #
    @api.model_create_multi
    def create(self, vals_list):
        wait_time = self._get_appointment_wait_time()
        # wait_display_event = self._get_appointment_wait_to_show_event()
        for vals in vals_list:
            vals.setdefault('appointment_wait_time', wait_time)
            # vals.setdefault('appointment_show_wait_time', wait_display_event)

            base_date = fields.Datetime.now()
            vals.setdefault(
                'appointment_min_date',
                base_date + timedelta(minutes=vals['appointment_wait_time'])
            )

        return super().create(vals_list)
