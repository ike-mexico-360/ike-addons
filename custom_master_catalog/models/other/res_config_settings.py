# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    events_allow_send_whatsapp = fields.Boolean(
        string='(Custom) Send whatsapp notifications',
        compute='_compute_events_allow_send_whatsapp',
        inverse='_inverse_events_allow_send_whatsapp',
    )
    x_default_purchase_project_id = fields.Many2one(
        comodel_name='project.project',
        required=True,
        related='company_id.x_default_purchase_project_id',
        string='Default Purchase Project',
        help="Technical: Default purchase project linked to the company at consolidate and send SAP data.",
        ondelete='restrict',
        readonly=False,
    )
    x_allow_email_sending = fields.Boolean(
        related='company_id.x_allow_email_sending',
        readonly=False,
        string='Allow Email Sending',
    )

    def _compute_events_allow_send_whatsapp(self):
        for setting in self:
            setting.events_allow_send_whatsapp = self.env['ir.config_parameter'].sudo().get_param('events.allow_send_whatsapp')

    def _inverse_events_allow_send_whatsapp(self):
        self.env['ir.config_parameter'].sudo().set_param('events.allow_send_whatsapp', self.events_allow_send_whatsapp)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res['events_allow_send_whatsapp'] = bool(self.env['ir.config_parameter'].sudo().get_param('events.allow_send_whatsapp'))
        return res
