# -*- coding: utf-8 -*-

from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    x_afirme_portal_access = fields.Boolean(
        string='AFIRME dashboard access',
        help='Allows this portal user to view the AFIRME dashboard.',
        default=False,
    )
