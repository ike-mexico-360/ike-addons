# -*- coding: utf-8 -*-
from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    signup_type = fields.Char(
        groups="base.group_erp_manager,ike_event_portal.custom_group_portal_admin"
    )
