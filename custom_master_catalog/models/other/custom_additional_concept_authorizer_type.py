# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomAdditionalConceptAuthorizerType(models.Model):
    _name = 'custom.additional.concept.authorizer.type'
    _description = 'Additional Concept Authorizer Types'
    _inherit = ['mail.thread']

    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)
    name = fields.Char('Name', required=True, tracking=True)
    description = fields.Text('Description', tracking=True)
    is_user_internal = fields.Boolean('User internal', default=False, tracking=True)
    is_nu = fields.Boolean('NU', default=False, tracking=True)
    is_client = fields.Boolean('Client', default=False, tracking=True)

    # === CONSTRAINT METHODS === #
    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            domain = [
                ('name', '=', rec.name),
                ('id', '!=', rec.id)
            ]
            if self.search_count(domain) > 0:
                raise ValidationError(_('A record with the same name already exists.'))

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