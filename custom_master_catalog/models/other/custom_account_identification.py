# -*- coding: utf-8 -*-

import re

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomAccountIdentification(models.Model):
    _name = 'custom.account.identification'
    _description = 'Account Identification'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, tracking=True)
    description = fields.Text(tracking=True)

    regex = fields.Char(tracking=True)
    label = fields.Char(required=True, tracking=True)
    clause = fields.Boolean(string="Clause")

    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    @api.constrains('label')
    def _check_label(self):
        pattern = re.compile(r'^[A-Za-z0-9 ]+$')
        # pattern = re.compile(r'^[A-Za-z0-9]+$')
        for rec in self:
            if rec.label and not pattern.match(rec.label):
                raise ValidationError(_('Label can only contain letters, numbers, and spaces.'))

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
