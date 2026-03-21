# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api
import random


class HelpdeskTags(models.Model):
    _name = 'helpdesk.tags'
    _description = 'Helpdesk Tags'
    _rec_name = 'name'

    name = fields.Char("Name", required=True, translate=True)
    color = fields.Integer(string='Color Index')

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists!"),
    ]

    @api.model_create_multi
    def create(self, vals):
        res = super(HelpdeskTags, self).create(vals)
        number = random.randrange(1, 10)
        res.color = number
        return res
