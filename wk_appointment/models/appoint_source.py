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


class AppointmentSource(models.Model):
    _name = 'appointment.source'
    _description = "Appointment Source"

    name = fields.Char("Source", required=True)
    company_id = fields.Many2one('res.company', 'Company', default=lambda self:self.env.user.company_id)
