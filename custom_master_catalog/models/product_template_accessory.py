# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_accessory_ok = fields.Boolean(
        string="Accessory", compute='_compute_x_accessory_ok', inverse='_set_x_accessory_ok',
        search='_search_x_accessory_ok')

    @api.depends('product_variant_ids.x_accessory_ok')
    def _compute_x_accessory_ok(self):
        self._compute_template_field_from_variant_field('x_accessory_ok')

    def _set_x_accessory_ok(self):
        self._set_product_variant_field('x_accessory_ok')

    def _search_x_accessory_ok(self, operator, value):
        return [('product_variant_ids.x_accessory_ok', operator, value)]


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_accessory_ok = fields.Boolean(string="Accessory", tracking=True)

    @api.constrains('name', 'sale_ok', 'sh_product_subscribe', 'purchase_ok', 'x_accessory_ok', 'categ_id', 'uom_id')
    def chec_unique_accessory(self):
        for rec in self:
            domain = rec.get_accessories_domain()
            if self.search_count(domain + [('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', False)]) > 0:
                raise ValidationError(_('A record with the same name already exists.'))
            elif self.search_count(domain + [('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', True)]) > 0:
                raise ValidationError(_('A record with the same name already exists. It is disabled.'))

    def get_accessories_view_action(self):
        action = self.env['ir.actions.act_window']._for_xml_id('custom_master_catalog.custom_ike_accessories_action')
        all_categ_id = self.env.ref('product.product_category_all')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        ctx = eval(action['context'])
        ctx.update({
            'default_categ_id': all_categ_id.id,
            'default_uom_id': service_uom_id.id,
        })
        action.update({'domain': self.get_accessories_domain(), 'context': ctx})
        return action

    @api.model
    def get_accessories_domain(self):
        all_categ_id = self.env.ref('product.product_category_all')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        return [
            ('sale_ok', '=', False),
            ('sh_product_subscribe', '=', False),
            ('purchase_ok', '=', True),
            ('x_accessory_ok', '=', True),
            ('type', '=', 'service'),
            ('list_price', '=', 0),
            ('standard_price', '=', 0),
            ('categ_id', '=', all_categ_id.id),
            ('uom_id', '=', service_uom_id.id),
        ]

    @api.model
    def repair_missing_values_accessories(self):
        all_categ_id = self.env.ref('product.product_category_all')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        product_ids = self.env['product.product'].search([
            ('product_tmpl_id.sale_ok', '=', False),
            ('product_tmpl_id.sh_product_subscribe', '=', False),
            ('product_tmpl_id.purchase_ok', '=', True),
            ('product_tmpl_id.x_accessory_ok', '=', True),
            ('product_tmpl_id.type', '=', 'service'),
            ('product_tmpl_id.list_price', '=', 0),
            ('product_tmpl_id.standard_price', '=', 0),
            ('product_tmpl_id.categ_id', '=', all_categ_id.id),
            ('product_tmpl_id.uom_id', '=', service_uom_id.id),
        ])
        product_ids.write({
            'sale_ok': False,
            'sh_product_subscribe': False,
            'purchase_ok': True,
            'x_accessory_ok': True,
            'type': 'service',
            'list_price': 0,
            'standard_price': 0,
            'categ_id': all_categ_id.id,
            'uom_id': service_uom_id.id,
        })

    # Heredamos el método _creation_message para modificar el mensaje de creación
    def _creation_message(self):
        self.ensure_one()
        if self.env.context.get('x_accessories_view'):
            return _("Accessory created")
        return super()._creation_message()
