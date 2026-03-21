from odoo import models, fields, _
from markupsafe import Markup


class ResCountry(models.Model):
    _name = 'res.country'
    _inherit = ['res.country', 'mail.thread']

    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    name = fields.Char(tracking=True)
    currency_id = fields.Many2one(tracking=True)
    code = fields.Char(tracking=True)
    phone_code = fields.Integer(tracking=True)
    zip_required = fields.Boolean(tracking=True)

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
