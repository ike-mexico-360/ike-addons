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

from odoo import models, fields, api, _
import logging
_logger = logging.getLogger(__name__)
from odoo.exceptions import UserError


class AppointmentGroup(models.Model):
    _name = 'appointment.person.group'
    _rec_name = 'group_name'
    _description = "Appointment Group"

    group_image = fields.Binary(string= "Group Image")
    group_name = fields.Char("Group")
    appoint_person_ids = fields.Many2many(
        comodel_name= "res.partner",
        relation= "appoint_partner_table",
        column1= "appoint_group_id",
        column2= "res_partner_id",
        string="Appointment Person",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )
    color = fields.Integer(string='Color Index')
    appoint_members_count = fields.Integer(
        " Total Appointment Members",
        compute="count_appoint_persons"
    )
    general = fields.Boolean("General", default=False)
    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.user.company_id.currency_id
    )
    company_id = fields.Many2one('res.company', 'Company', default=lambda self:self.env.user.company_id)
    group_charge = fields.Float("Appointment Charge")
    product_tmpl_id = fields.Many2one(
        "product.template",
        "Group Product",
        help="This product will be used for applying appointment\
        charges while booking an appointment."
    )
    active = fields.Boolean(
        'Active',
        default=True,
        help="If unchecked, it will allow you to hide this record without removing it."
    )

    def count_appoint_persons(self):
        for rec in self:
            rec.appoint_members_count = len(rec.appoint_person_ids)
        return True

    def appoint_update_product_price(self):
        for rec in self:
            if rec.product_tmpl_id and rec.product_tmpl_id.list_price != rec.group_charge:
                rec.product_tmpl_id.write({'list_price': rec.group_charge})
        return True

    def write(self, vals):
        if vals.get('group_charge') and vals.get('group_charge') < 0:
            raise UserError(_("Group charge cannot be less than zero"))
        res = super(AppointmentGroup, self).write(vals)
        if vals.get("product_tmpl_id") or "group_charge" in vals and vals.get("group_charge") >= 0:
            self.appoint_update_product_price()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('group_charge') and vals.get('group_charge') < 0:
                raise UserError(_("Group charge cannot be less than zero"))
            res = super(AppointmentGroup, self).create(vals)
            res.appoint_update_product_price()
            return res
