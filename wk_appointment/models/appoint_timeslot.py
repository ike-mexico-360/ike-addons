# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# License URL : https://store.webkul.com/license.html/
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################

from odoo import models,fields,api,_
from odoo.exceptions import UserError
import logging, math
_logger = logging.getLogger(__name__)


class AppointTimeslot(models.Model):
    _name = "appointment.timeslot"
    _description = "Appointment TimeSlot"
    _order = "start_time"

    desc = fields.Text(string="Description")
    start_time = fields.Float(string="Start Time", required =True)
    end_time = fields.Float(string="End Time", required=True)
    name = fields.Char(string="Slot", required=True, compute="compute_rec_name")
    timerange = fields.Char()
    active = fields.Boolean(
        'Active',
        default=True,
        help="If unchecked, it will allow you to hide this record without removing it."
    )
    company_id = fields.Many2one('res.company', 'Company', default=lambda self:self.env.user.company_id)

    # SQL Constraints
    _sql_constraints = [
        ('timeslot_day_starttime_endtime_unique', 'unique(start_time, end_time)', _('This slot already exist.'))
    ]

    @api.depends("start_time", "end_time")
    def name_get(self):
        result = []
        for rec in self:
            start_time = rec.float_time_convert(rec.start_time)
            end_time = rec.float_time_convert(rec.end_time)
            timerange = ' (' + str(start_time) + ' - ' + str(end_time) + ')'
            result.append((rec.id, timerange))
        return result

    @api.onchange("start_time", "end_time")
    def compute_rec_name(self):
        for rec in self:
            rec.name = rec.name_get()[0][1]

    def float_time_convert(self, float_val):
        """convert float to float_time so visible in front end."""
        factor = float_val < 0 and -1 or 1
        val = abs(float_val)
        hours = factor * int(math.floor(val))
        minutes = int(round((val % 1) * 60))
        if minutes == 60:
            minutes = 0
            hours = hours + 1
        return ("%s:%s" % (str(hours).zfill(2), str(minutes).zfill(2)))

    def check_time_values(self, vals):
        start_time = vals.get('start_time') if vals.get('start_time') else self.start_time
        end_time = vals.get('end_time') if vals.get('end_time') else self.end_time
        if start_time:
            if start_time >= 24 or start_time < 0:
                raise UserError(_("Please enter a valid hour between 00:00 and 24:00"))
        if end_time:
            if end_time >= 24 or end_time < 0:
                raise UserError(_("Please enter a valid hour between 00:00 and 24:00"))
        if start_time >= end_time or start_time == end_time:
            raise UserError(_("The start time should be less than end time."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self.check_time_values(vals)
            res = super(AppointTimeslot, self).create(vals)
            return res

    def write(self, vals):
        self.check_time_values(vals)
        res = super(AppointTimeslot, self).write(vals)
        return res

    def compute_timerange(self):
        start_time = self.float_time_convert(self.start_time)
        end_time = self.float_time_convert(self.end_time)
        self.timerange = self.name + ' (' + str(start_time) + ' - ' + str(end_time) + ')'
        return True
