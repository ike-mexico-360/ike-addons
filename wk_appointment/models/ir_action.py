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


APPOINT_DOMAIN_STRING = "get_appointee_id()"


class IrActionWindow(models.Model):
    _inherit = 'ir.actions.act_window'


    def update_appoint_dynamic_domain(self, res):
        if not res:
            return res
        obj_user = self.env.user
        try:
            for r in res:
                wk_appoint_dynamic_domain = r.get("domain", [])
                if wk_appoint_dynamic_domain and APPOINT_DOMAIN_STRING in wk_appoint_dynamic_domain:
                    domain_list = eval(wk_appoint_dynamic_domain)
                    list_of_index = [index for index, appoint_tuple in enumerate(domain_list) if APPOINT_DOMAIN_STRING in str(appoint_tuple[2])]
                    updated_domain = ""
                    if obj_user.has_group('wk_appointment.appointment_officer_group'):
                        for index in list_of_index:
                            var = domain_list[index][0]
                            if var == "id":
                                domain_list.pop(index)
                            else:
                                domain_list[index] = (var, '!=', False)
                        updated_domain = str(domain_list)
                    else:
                        appointee_id = obj_user.partner_id.id
                        for index in list_of_index:
                            var = domain_list[index][0]
                            if var == "id":
                                r["view_mode"] = "form"
                                r["res_id"] = appointee_id
                                r["views"] = [(self.env.ref('wk_appointment.inherit_view_partner_form').id, "form")]
                            domain_list[index] = (var, 'in', [appointee_id])
                        updated_domain = str(domain_list)
                    if APPOINT_DOMAIN_STRING in (r.get('domain', '[]') or ''):
                        r['domain'] = updated_domain
        except Exception as e:
            _logger.info("~~~~~~~~~~Exception~~~~~~~~%r~~~~~~~~~~~~~~~~~", e)
            pass
        return res

    def read(self, fields=None, load='_classic_read'):
        res = super(IrActionWindow, self).read(fields=fields, load=load)
        return self.update_appoint_dynamic_domain(res)
