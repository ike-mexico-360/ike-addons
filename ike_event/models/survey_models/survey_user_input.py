# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SurveyUserInput(models.Model):
    _inherit = 'survey.user_input'

    event_id = fields.Many2one('ike.event', readonly=True)

    def set_event_summary_survey_data(self):
        """Survey Data"""
        for rec in self:
            survey_data = rec.event_id.event_summary_id.survey_data
            fields = survey_data.get('fields', [])
            fields.extend(
                [
                    {
                        'name': f"{answer_id.id}_{answer_id.question_id.id}",
                        'string': answer_id.question_id.title,
                        'type': 'html',
                        'value': (
                            int(answer_id.value_numerical_box)
                            if answer_id.value_numerical_box
                            and answer_id.value_numerical_box.is_integer()
                            else answer_id.display_name
                        ),
                    }
                    for answer_id in rec.user_input_line_ids
                ]
            )
            survey_data['fields'] = fields
            rec.event_id.event_summary_id.survey_data = survey_data
