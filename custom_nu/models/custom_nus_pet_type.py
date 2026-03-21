# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomNusPetType(models.Model):
    _name = 'custom.nus.pet.type'
    _description = 'Pet Type'
    _inherit = ['mail.thread']

    # === FIELDS === #
    active = fields.Boolean(string='Active', default=True)
    disabled = fields.Boolean(string='Disabled', default=False)
    name = fields.Char(string='Name', required=True, tracking=True)

    # === CONSTRAINTS === #
    @api.constrains('name')
    def _check_unique_name(self):
        for record in self:
            if self.search_count([('name', '=', record.name)]) > 1:
                raise ValidationError(
                    _("The name must be unique.")
                )

    # === ACTIONS === #
    def action_disable(self, reason=None):
        for rec in self:
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
                rec.message_post(
                    body=body,
                    message_type='notification',
                    body_is_html=True)
        return super().action_disable(reason)
