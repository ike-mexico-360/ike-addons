# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import models, fields, api, _


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def notify_disabled(self, reason=None):
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
