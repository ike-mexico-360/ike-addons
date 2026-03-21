# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IkeServiceMedicalConsultation(models.Model):
    _name = 'ike.service.input.medical.consultation'
    _inherit = ['ike.service.input']
    _description = 'Service Input Medical Consultation'

    consultation_type = fields.Selection([
        ('general', 'General Consultation'),
        ('specialist', 'Specialist Consultation'),
        ('follow_up', 'Follow-up Consultation'),
    ], string='Consultation Type', default='general', required=True)
