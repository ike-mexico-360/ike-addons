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

from odoo import models, _
import logging
_logger = logging.getLogger(__name__)


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    def update_wk_appoint_menus(self, res):
        if not res:
            return res
        if self.env.user.has_group('wk_appointment.appointment_appointee_group') and not self.env.user.has_group('wk_appointment.appointment_officer_group'):
            appointee_menu_id = self.env['ir.model.data']._xmlid_lookup('wk_appointment.appoint_mgmt_customer_menu')[1]
            for dictionary in res:
                if dictionary.get("id", False) == appointee_menu_id:
                    dictionary["name"] = _("Appointee")
        return res

    def read(self, list1, load="_classic_read"):
        res = super(IrUiMenu, self).read(list1, load)
        return self.update_wk_appoint_menus(res)
