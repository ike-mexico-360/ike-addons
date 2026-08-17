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

from odoo import tools
from odoo import models, fields, api
import logging
log = logging.getLogger(__name__)

class AppointmentReport(models.Model):
    _name = "appointment.report"
    _description = "Appointment Statistics"
    _auto = False
    _order = 'date desc'
    _rec_name = 'date'

    date = fields.Date("Create Date", readonly=True)
    appoint_date = fields.Date("Appointment Date", readonly=True)
    appoint_product_id = fields.Many2one('product.product', string='Product', readonly=True)
    appoint_group_id = fields.Many2one("appointment.person.group", string="Appointment Group", readonly=True)
    appoint_person_id = fields.Many2one('res.partner', string='Group Member', readonly=True)
    customer = fields.Many2one('res.partner', string='Customer', readonly=True)
    price_total = fields.Float(string='Total With Tax', readonly=True)
    price_subtotal = fields.Float(string='Total Without Tax', readonly=True)
    nbr = fields.Integer(string='# of Lines', readonly=True)
    time_slot_day = fields.Char("Day")
    source = fields.Many2one('appointment.source', string="Source")
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    appoint_state = fields.Selection([
        ('new', 'new'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('done', 'Done')
    ], string='Appointment State', readonly=True)

    _depends = {
        'appointment': [
            'amount_total', 'customer', 'currency_id', 'company_id',
            'appoint_group_id', 'appoint_date', 'create_date',
            'appoint_state','time_slot_day','appoint_person_id'
        ],
        'appointment.lines': [
            'appoint_id', 'price_subtotal', 'appoint_product_id', 'product_qty', 'price_tax', 'price_total'
        ],
        'product.product': ['product_tmpl_id'],
        'product.template': ['categ_id'],
        'res.currency.rate': ['currency_id', 'name'],
        'res.partner': ['country_id'],
    }

    def _select(self):
        select_str = """
            SELECT sub.id, sub.source, sub.customer, sub.appoint_date,sub.date,
                sub.appoint_group_id, sub.company_id, sub.appoint_person_id,sub.appoint_product_id,
                sub.price_total as price_total,sub.price_subtotal as price_subtotal,
                sub.time_slot_day,sub.currency_id,sub.appoint_line_id,sub.appoint_state,
                COALESCE(cr.rate, 1) as currency_rate,sub.nbr
        """
        return select_str

    def _sub_select(self):
        select_str = """
                SELECT apl.id AS id,
                    ap.create_date AS date,
                    ap.time_slot_day, ap.currency_id,
                    apl.appoint_product_id, ap.customer, ap.appoint_group_id, ap.appoint_person_id, ap.company_id,
                    ap.source, 1 AS nbr,ap.appoint_date,
                    SUM(apl.price_total) AS price_total,
                    SUM(apl.price_subtotal) AS price_subtotal,
                    apl.appoint_id AS appoint_line_id,
                    ap.appoint_state
        """
        return select_str

    def _from(self):
        from_str = """
                FROM appointment_lines apl
                JOIN appointment ap ON ap.id = apl.appoint_id
                JOIN res_partner partner ON ap.appoint_person_id = partner.id
                JOIN appointment_person_group gp ON ap.appoint_group_id = gp.id
                LEFT JOIN product_product pr ON pr.id = apl.appoint_product_id
                LEFT JOIN product_template pt ON pt.id = pr.product_tmpl_id
        """
        return from_str

    def _group_by(self):
        group_by_str = """
                GROUP BY apl.id, apl.appoint_product_id, ap.id,
                    ap.appoint_person_id, ap.company_id, ap.appoint_group_id,
                    ap.customer, ap.appoint_state, ap.source,
                    ap.amount_total,ap.appoint_date,ap.create_date,
                    ap.time_slot_day
        """
        return group_by_str

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        query = """CREATE or REPLACE VIEW %s as (
            WITH currency_rate AS (%s)
            %s
            FROM (
                %s %s %s
            ) AS sub
            LEFT JOIN currency_rate cr ON
                (cr.currency_id = sub.currency_id AND
                cr.company_id = sub.company_id AND
                 cr.date_start <= COALESCE(sub.date, NOW()) AND
                 (cr.date_end IS NULL OR cr.date_end > COALESCE(sub.date, NOW())))
        )""" % (
                    self._table, self.env['res.currency']._select_companies_rates(),
                    self._select(), self._sub_select(), self._from(), self._group_by())
        self.env.cr.execute(query)
