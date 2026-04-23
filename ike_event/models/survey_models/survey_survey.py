from odoo import models, fields


class SurveySurvey(models.Model):
    _inherit = 'survey.survey'

    x_show_final_score = fields.Boolean(
        string="Show Final Score",
        default=True,
        tracking=True,
        help="Show final score in survey (Odoo default workflow show always the final score)")
