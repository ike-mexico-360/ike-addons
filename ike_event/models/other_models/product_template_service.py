from odoo import models, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_survey_id = fields.Many2one('survey.survey', string='Survey')
    x_icon = fields.Char(string='Icon ')
    x_input_res_model = fields.Selection([
        ('ike.service.input.vial.truck', 'Town Truck'),
        ('ike.service.input.vial.generic', 'Vial Generic'),
        ('ike.service.input.medical.consultation', 'Consultation'),
        ('ike.service.input.generic.sub', 'Generic'),
    ], string='Input Model')
    x_is_origin_destination = fields.Boolean(string='Is Origin - Destination', default=False, tracking=True)
    x_signature_required = fields.Boolean(string='Signature required', default=False, tracking=True)
    x_generate_appointment = fields.Boolean(string="Generate Appointment")
