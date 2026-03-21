from odoo import models, fields


class ProductCategory(models.Model):
    _inherit = 'product.category'

    x_ref = fields.Char(string='Ref')
    x_survey_id = fields.Many2one('survey.survey', string='Survey')
    x_icon = fields.Char(string='Icon')
    x_input_res_model = fields.Selection([
        ('ike.service.input.vial', 'Vial'),
        ('ike.service.input.medical', 'Medical'),
        ('ike.service.input.generic', 'Generic'),
    ], string='Input Model')
