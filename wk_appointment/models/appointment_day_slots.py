from odoo import fields, models, api
import math
import re
from odoo.exceptions import ValidationError
from collections import Counter

import logging
_logger = logging.getLogger(__name__)


class AppointmentDaySlots(models.Model):
    _name = 'appointment.day.slots'
    _description = 'Appointment Day Slots'

    day = fields.Selection([
        ('sunday', 'Sunday'),
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),],
        string="Day",
        required=True
    )

    appointee_id = fields.Many2one("res.partner",string="Appointee",readonly=True)
    time_slots_ids = fields.Many2many("appointment.timeslot")

    @api.onchange('day')
    def check_similar_day(self):
        self.appointee_id and self.appointee_id.id
        appointee_str = str(self.appointee_id.id)
        match = re.search(r'\d+', appointee_str)
        partner_id = match.group(0)
        partner_appointment_day_slots = self.env['appointment.day.slots'].search([('appointee_id.id', '=', partner_id)])
        for day_slot in partner_appointment_day_slots:
            if day_slot.day == self.day:
                raise ValidationError("Please select a different day as the slots are already available for the chosen day.")

    def create(self, vals):
        days_list = [rec['day'] for rec in vals]  # List comprehension for efficiency
        counter = Counter(days_list)
        duplicates = [day.capitalize() for day, count in counter.items() if count > 1]
        if duplicates:
            raise ValidationError(f"Please select a different day as the following days are already selected: {', '.join(duplicates)}")
        return super().create(vals)
