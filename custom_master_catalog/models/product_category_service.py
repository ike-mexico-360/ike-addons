# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class ProductCategory(models.Model):
    _inherit = 'product.category'
    _description = 'Services'

    # === FIELDS === #
    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    # Redefinition of 'name' to enable change tracking
    name = fields.Char('Name', index='trigram', required=True, tracking=True)
    description = fields.Char('Description', tracking=True, size=250, help="Service description")
    operation_area_id = fields.Many2one(
        'custom.service.operational.area',
        'Operational Area'
    )
    x_color = fields.Integer(string='Color')

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if self.search_count([('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', False)]) > 0:
                raise ValidationError(_('A record with the same name already exists.'))
            elif self.search_count([('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', True)]) > 0:
                raise ValidationError(_('A record with the same name already exists. It is disabled.'))

    # === COMPUTE === #
    @api.depends_context('hierarchical_naming')
    def _compute_display_name(self):
        """
        Compute the display name for product categories with two possible modes:

        1. Hierarchical mode (full path):
        - Activated by passing {'hierarchical_naming': True} in the context
        - Shows complete path (e.g., "All/Asistencia/Vial")
        - Uses the standard Odoo name_get behavior

        2. Simple mode (name only - default):
        - When no context or {'hierarchical_naming': False}
        - Shows only the category name (e.g., "Vial")

        Usage in XML views:
        - For hierarchical display: <field name="category_id" context="{'hierarchical_naming': True}"/>
        - For simple display (default): <field name="category_id"/>
        """
        """
        Compute the display name for product categories with two possible modes:

        1. Hierarchical mode (full path):
        - Activated by passing {'hierarchical_naming': True} in the context
        - Shows complete path (e.g., "All/Asistencia/Vial")
        - Uses the standard Odoo name_get behavior

        2. Simple mode (name only - default):
        - When no context or {'hierarchical_naming': False}
        - Shows only the category name (e.g., "Vial")

        Usage in XML views:
        - For hierarchical display: <field name="category_id" context="{'hierarchical_naming': True}"/>
        - For simple display (default): <field name="category_id"/>
        """
        if self.env.context.get('hierarchical_naming', False):
            return super()._compute_display_name()
        for record in self:
            record.display_name = record.name

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
