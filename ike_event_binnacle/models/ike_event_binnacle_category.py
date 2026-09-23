# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup


class IkeEventBinnacleCategory(models.Model):
    _name = 'ike.event.binnacle.category'
    _inherit = ['mail.thread']
    _description = 'Event Binnacle Category'
    _rec_name = 'name'

    name = fields.Char(required=True, tracking=True, translate=True)
    parent_id = fields.Many2one('ike.event.binnacle.category', tracking=True)
    child_id = fields.One2many('product.category', 'parent_id', 'Child Categories')

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

    _sql_constraints = [(
        'name_uniq',
        "unique(name)",
        "A category with the same name already exists."
    )]

    @api.constrains('parent_id')
    def _check_category_recursion(self):
        if self._has_cycle():
            raise ValidationError(_('You cannot create recursive categories.'))

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
