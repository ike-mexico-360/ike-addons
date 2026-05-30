# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    x_bp_tenant = fields.Char(
        string='Bright Pattern Tenant URL',
        compute='_compute_x_bp_tenant',
        inverse='_inverse_x_bp_tenant',
    )
    x_bp_default_service = fields.Char(
        string='Bright Pattern Default Service',
        compute='_compute_x_bp_default_service',
        inverse='_inverse_x_bp_default_service',
    )

    def _compute_x_bp_tenant(self):
        for setting in self:
            setting.x_bp_tenant = self.env['ir.config_parameter'].sudo().get_param('ike_event.bp_tentant')

    def _inverse_x_bp_tenant(self):
        self.env['ir.config_parameter'].sudo().set_param('ike_event.bp_tenant', self.x_bp_tenant)

    def _compute_x_bp_default_service(self):
        for setting in self:
            setting.x_bp_default_service = self.env['ir.config_parameter'].sudo().get_param('ike_event.bp_default_service')

    def _inverse_x_bp_default_service(self):
        self.env['ir.config_parameter'].sudo().set_param('ike_event.bp_default_service', self.x_bp_default_service)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        res.update({
            'x_bp_tenant': self.env['ir.config_parameter'].sudo().get_param('ike_event.bp_tenant'),
            'x_bp_default_service': self.env['ir.config_parameter'].sudo().get_param('ike_event.bp_default_service'),
        })
        return res
