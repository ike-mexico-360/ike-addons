# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomNusPetBreed(models.Model):
    _name = 'custom.nus.pet.breed'
    _description = 'Pet Breed'
    _inherit = ['mail.thread']

    # === FIELDS === #
    active = fields.Boolean(string='Active', default=True)
    disabled = fields.Boolean(string='Disabled', default=False)
    name = fields.Char(string='Name', required=True, tracking=True)
    pet_type_id = fields.Many2one('custom.nus.pet.type', string='Pet Type', required=True, tracking=True)

    # === CONSTRAINTS === #
    @api.constrains('name', 'pet_type_id')
    def _check_unique_name(self):
        for record in self:
            if self.search_count([
                ('name', '=', record.name),
                ('pet_type_id', '=', record.pet_type_id.id),
                ('id', '<>', record.id)
            ]) > 0:
                raise ValidationError(
                    _("The combination of breed and type must be unique.")
                )

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
