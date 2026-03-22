# -*- coding: utf-8 -*-

from odoo import models, fields


class CustomServiceOperationalArea(models.Model):
    _name = 'custom.service.operational.area'
    _description = 'Service Operational Area'

    name = fields.Char(string='Name')

    active = fields.Boolean('Active', default=True)
    disabled = fields.Boolean('Disabled', default=False)
