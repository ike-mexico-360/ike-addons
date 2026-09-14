# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import timedelta


class IkeServiceInputVialBase(models.AbstractModel):
    _inherit = 'ike.service.input.vial.base'

    scheduled = fields.Boolean(
        related='event_id.scheduled',  # type: ignore
        readonly=False,
    )

    event_date = fields.Datetime(
        related='event_id.event_date',
        readonly=False,
    )

    appointment_wait_time = fields.Integer(
        related='event_id.appointment_wait_time'
    )

    appointment_min_date = fields.Datetime(
        related='event_id.appointment_min_date',
        readonly=True,
    )

    selected_ongoing_suppliers = fields.Integer(
        related='event_id.selected_ongoing_suppliers',  # type: ignore
        readonly=True,
    )

    @api.onchange('scheduled')
    def onchange_scheduled(self):
        if self.scheduled:
            base_date = fields.Datetime.now()
            self.appointment_min_date = base_date + timedelta(minutes=self.appointment_wait_time)
            self.event_date = self.appointment_min_date
