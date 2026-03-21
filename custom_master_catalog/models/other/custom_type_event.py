# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup


class CustomTypeEvent(models.Model):
    _name = 'custom.type.event'
    _description = 'Type of Event'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    description = fields.Char(tracking=True)
    requires_federal_plates = fields.Boolean(default=False, tracking=True)

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)
