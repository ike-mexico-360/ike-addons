# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup


class CustomSupplierType(models.Model):
    _name = 'custom.supplier.type'
    _description = 'Supplier Type'
    _inherit = ['mail.thread']

    name = fields.Char(required=True, tracking=True)
    description = fields.Char(tracking=True)

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

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
