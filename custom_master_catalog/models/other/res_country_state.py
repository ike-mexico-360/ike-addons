from odoo import models, fields, _
from markupsafe import Markup


class ResCountryState(models.Model):
    _name = 'res.country.state'
    _inherit = ['res.country.state', 'mail.thread']

    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    name = fields.Char(tracking=True)
    code = fields.Char(tracking=True)
    country_id = fields.Many2one(tracking=True)
    c_estado = fields.Char(string='Sepomex estado')

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
