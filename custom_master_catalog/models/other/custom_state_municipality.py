# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup


class CustomStateMunicipality(models.Model):
    _name = 'custom.state.municipality'
    _description = 'Municipality'
    _inherit = ['mail.thread']

    name = fields.Char(required=True)
    country_id = fields.Many2one('res.country', required=True, index=True)
    state_id = fields.Many2one('res.country.state', required=True, index=True)
    red_zone = fields.Boolean(default=False, tracking=True)
    c_estado = fields.Integer(string='Sepomex estado', required=True)
    c_mnpio = fields.Integer(string='Sepomex municipio', required=True)
    c_delta = fields.Char(compute='_compute_c_delta', store=True, index='trigram')
    disabled = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    code_ids = fields.One2many('custom.state.municipality.code', 'municipality_id', string='ZIP Codes')

    # === COMPUTES === #
    @api.depends('c_estado', 'c_mnpio')
    def _compute_c_delta(self):
        for rec in self:
            rec.c_delta = str(rec.c_estado).zfill(2) + str(rec.c_mnpio).zfill(3)

    # === ACTIONS === #
    def action_disable(self, reason=None):
        if reason:
            body = Markup("""
                <ul class="mb-0 ps-4">
                    <li>
                        <b>{}: </b><span class="">{}</span>
                    </li>
                </ul>
            """).format(
                _('Disabled'),
                reason,
            )
            self.message_post(
                body=body,
                message_type='notification',
                body_is_html=True)
        return super().action_disable(reason)


class CustomStateMunicipalityCode(models.Model):
    _name = 'custom.state.municipality.code'
    _description = 'Municipality ZIP'
    _rec_name = 'zip_code'

    municipality_id = fields.Many2one('custom.state.municipality', required=True)
    zip_code = fields.Char(string='ZIP', required=True, index=True)
    city = fields.Char()

    disabled = fields.Boolean(default=False)
    active = fields.Boolean(default=True)


class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    disabled = fields.Boolean(default=False)
