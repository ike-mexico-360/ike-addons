# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class Custom_address_typePy(models.Model):
    _name = "custom.address.type"
    _description = "Custom address type"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Name", tracking=True, required=True)
    description = fields.Text(string="Description", tracking=True)
    active = fields.Boolean(string="Active", default=True, tracking=True)
    disabled = fields.Boolean(string="Disabled", default=False, tracking=True)

    @api.constrains("name")
    def _check_unique_name(self):
        for rec in self:
            domain = [("name", "=", rec.name), ("id", "!=", rec.id)]
            if self.search_count(domain) > 0:
                raise ValidationError(_("A record with the same name already exists."))

    def action_disable(self, reason=None):
        for rec in self:
            if reason:
                body = Markup(
                    """
                    <ul class="mb-0 ps-4">
                        <li>
                            <b>{}: </b><span class="">{}</span>
                        </li>
                    </ul>
                """
                ).format(
                    _("Disabled"),
                    reason,
                )
                rec.message_post(
                    body=body, message_type="notification", body_is_html=True
                )
        return super().action_disable(reason)
