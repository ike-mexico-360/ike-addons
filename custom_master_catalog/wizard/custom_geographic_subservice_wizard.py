
from odoo import api, models, fields, _


class CustomGeographicSubserviceWizard(models.TransientModel):
    _name = 'custom.geographic.subservice.wizard'
    _description = 'Custom geographic subservice wizard'

    partner_id = fields.Many2one('res.partner', string='Center of attention')
    state_id = fields.Many2one('res.country.state', string="Entity")
    municipality_id = fields.Many2one('custom.state.municipality', string="Municipality")
    event_type_id = fields.Many2one('custom.type.event', string='Event type')
