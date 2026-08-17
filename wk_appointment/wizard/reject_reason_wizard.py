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
import logging
_logger = logging.getLogger(__name__)


class AppointRejectReason(models.TransientModel):
    _name = "appoint.rejectreason.wizard"
    _description = "Appointment Reject Reason"

    add_reason = fields.Text(string="Reason for Rejection")

    def button_addreason(self):
        obj = self.env['appointment'].browse(self._context.get('active_ids'))
        if obj:
            add_reason = "Reason for Rejection of Appointment : " + self.add_reason
            obj.reject_appoint(add_reason)
        return
