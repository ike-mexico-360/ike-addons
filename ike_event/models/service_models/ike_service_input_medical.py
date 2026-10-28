# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IkeServiceMedical(models.Model):
    _name = 'ike.service.input.medical'
    _inherit = ['ike.service.input.model', 'mail.thread']
    _description = 'Service Input Medical'

    assigned = fields.Char(string='Doctor')
