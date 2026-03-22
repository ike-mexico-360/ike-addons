# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class SurveyQuestion(models.Model):
    _inherit = 'survey.question'

    x_send_to_operator = fields.Boolean('Send to Operator', default=False)
