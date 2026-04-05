# -*- coding: utf-8 -*-

from odoo import models, fields, _, api
from markupsafe import Markup


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_qty_period = fields.Integer(string='Cantidad periodo')
    x_unit_period = fields.Selection(
        [("day", "Día(s)"), ("week", "Semana(s)"), ("month", "Mes(es)"), ("year", "Año(s)")],
        default='day', string="Periodicidad")
    x_qty_reset_period = fields.Integer(string='Reseteo contador')
    x_unit_reset_period = fields.Selection(
        [("day", "Día(s)"), ("week", "Semana(s)"), ("month", "Mes(es)"), ("year", "Año(s)")],
        default='day', string="Periodicidad reseteo contador")
    x_date_reset = fields.Date(string='Fecha de Reseteo')
    x_cl_sub_service = fields.Integer('CL Sub Service')
    x_cost_by_km = fields.Boolean(string='Cost by Km', default=False)
    x_check_is_armor = fields.Boolean(string="Is armor?", tracking=True)
    x_armor_level = fields.Selection([
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5', '5'),
        ('6', '6'),
        ('7', '7'),
    ], string="level armor", tracking=True)

    @api.depends('name', 'default_code')
    def _compute_display_name(self):
        """Override display name to hide default_code for service products"""
        for record in self:
            # Si es un producto de servicio, no mostrar el código
            if record.type == 'service':
                record.display_name = record.name
            else:
                # Comportamiento por defecto de Odoo para otros tipos
                super(ProductProduct, record)._compute_display_name()

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
