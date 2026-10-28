from odoo import fields, models


class IkeSupportPlatform(models.Model):
    _name = 'ike.support.platform'
    _description = 'Support Platform'
    _order = 'sequence, name'

    name = fields.Char('Platform', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [('name_uniq', 'UNIQUE(name)', 'A platform with this name already exists.')]


class IkeSupportFailure(models.Model):
    _name = 'ike.support.failure'
    _description = 'Support Failure'
    _order = 'sequence, name'

    name = fields.Char('Failure', required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [('name_uniq', 'UNIQUE(name)', 'A failure with this name already exists.')]
