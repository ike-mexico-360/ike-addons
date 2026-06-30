# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_xml_max_days_old = fields.Integer(
        string="Max Allowed Days for XML Upload",
        default=30,
        help="Number of days allowed after the Purchase Order date to receive and upload the XML file."
    )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    x_xml_max_days_old = fields.Integer(
        related='company_id.x_xml_max_days_old',
        readonly=False,
        string="Max Allowed Days for XML Upload"
    )
