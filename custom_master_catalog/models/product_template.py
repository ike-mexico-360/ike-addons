# -*- coding: utf-8 -*-

from odoo import models, fields, _
from markupsafe import Markup


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    disabled = fields.Boolean(default=False, tracking=True)
    name = fields.Char(tracking=True)
    default_code = fields.Char(tracking=True)
    categ_id = fields.Many2one(tracking=True)
    uom_id = fields.Many2one(tracking=True)

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
