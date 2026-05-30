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

    @api.model
    def get_can_be_disabled(self):
        """ Inherit and override to restrict disabling capabilities based on specific user groups. """
        res = super().get_can_be_disabled()
        # List of allowed technical group XML IDs
        allowed_groups = [
            'base.group_system',
            'custom_master_catalog.custom_group_supplier_admin_system',
        ]
        has_permission = any(self.env.user.has_group(group) for group in allowed_groups)
        if not has_permission:
            return False
        return res

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
