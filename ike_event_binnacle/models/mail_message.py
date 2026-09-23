# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MailMessage(models.Model):
    _inherit = 'mail.message'

    supplier = fields.Char()
    event_binnacle_id = fields.Many2one('ike.event.binnacle')

    @api.onchange('event_binnacle_id')
    def _onchange_binnacle_id(self):
        if self.event_binnacle_id:
            self.body = self.event_binnacle_id.text_html
