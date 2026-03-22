# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields


class ResCompany(models.Model):
    _inherit = 'res.company'

    project_id = fields.Many2one('project.project', 'Default Project')
    sh_default_description = fields.Boolean(
        'Default Description In Timesheet ?')
    sh_multiple_ticket_allowed = fields.Boolean('Multiple Ticket Allowed ?')


class ResConfigSetting(models.TransientModel):
    _inherit = 'res.config.settings'

    project_id = fields.Many2one(
        'project.project', 'Default Project', readonly=False, related='company_id.project_id')
    sh_default_description = fields.Boolean(
        'Default Description In Timesheet ?', readonly=False, related='company_id.sh_default_description')
    sh_multiple_ticket_allowed = fields.Boolean(
        'Multiple Ticket Allowed ?', readonly=False, related='company_id.sh_multiple_ticket_allowed')
