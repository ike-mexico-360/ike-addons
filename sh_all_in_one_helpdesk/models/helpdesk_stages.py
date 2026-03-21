# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class HelpdeskStages(models.Model):
    _name = 'helpdesk.stages'
    _description = "Helpdesk Stages"
    _order = 'sequence ASC'
    _rec_name = 'name'

    name = fields.Char("Name", required=True,translate=True)
    mail_template_ids = fields.Many2many(
        'mail.template', string='Mail Template')
    sh_next_stage = fields.Many2one(
        comodel_name='helpdesk.stages',
        string='Next Stage',
    )

    sh_group_ids = fields.Many2many(
        comodel_name='res.groups',
        string='Groups'
    )
    is_cancel_button_visible = fields.Boolean(
        string='Is Cancel Button Visible ?'
    )
    is_done_button_visible = fields.Boolean(
        string='Is Resolved Button Visible ?'
    )
    sequence = fields.Integer(string="Sequence")
    color = fields.Char()
