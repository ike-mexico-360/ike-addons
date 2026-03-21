# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_mapping_ids = fields.One2many(
        'custom.product.mapping', string='Mappings', compute='_compute_x_mapping_ids', inverse='_set_x_mapping_ids')
    x_cl_sub_service = fields.Integer('CL Sub Service')
    x_description = fields.Char(string="Subservice description", tracking=True, size=250)

    sh_product_subscribe = fields.Boolean(
        string="Is Subscription Type",
        help="Click false to hide.",
        compute="_compute_sh_product_subscribe",
        inverse="_set_sh_product_subscribe",
        store=True,
        search="_search_sh_product_subscribe",
    )

    @api.depends('product_variant_ids.x_mapping_ids')
    def _compute_x_mapping_ids(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.x_mapping_ids = template.product_variant_ids.x_mapping_ids
            else:
                template.x_mapping_ids = False

    def _set_x_mapping_ids(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_mapping_ids = self.x_mapping_ids

    @api.depends("product_variant_ids.sh_product_subscribe")
    def _compute_sh_product_subscribe(self):
        """Compute the subscription flag based on the first product variant."""
        for template in self:
            template.sh_product_subscribe = (
                len(template.product_variant_ids) == 1 and template.product_variant_ids.sh_product_subscribe
            )

    def _search_sh_product_subscribe(self, operator, value):
        """Search for templates based on the subscription flag."""
        templates = self.with_context(active_test=False).search(
            [("product_variant_ids.sh_product_subscribe", operator, value)]
        )
        return [("id", "in", templates.ids)]

    def _set_sh_product_subscribe(self):
        """Set the subscription flag on product variants."""
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.sh_product_subscribe = self.sh_product_subscribe


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_mapping_ids = fields.One2many('custom.product.mapping', 'parent_id', string='Mappings')
    x_cl_sub_service = fields.Integer('CL Sub Service')
    x_description = fields.Char(string="Subservice description", tracking=True, size=250)
    sh_product_subscribe = fields.Boolean(
        string="Is Subscription Type", help="Click false to hide."
    )

    @api.constrains('name', 'sale_ok', 'sh_product_subscribe', 'purchase_ok', 'x_accessory_ok', 'categ_id', 'uom_id')
    def _check_unique_subservice(self):
        for rec in self:
            domain = rec.get_subservices_domain()
            if self.search_count(domain + [('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', False)]) > 0:
                raise ValidationError(_('A record with the same name already exists.'))
            elif self.search_count(domain + [('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', True)]) > 0:
                raise ValidationError(_('A record with the same name already exists. It is disabled.'))

    def get_subservices_view_action(self):
        action = self.env['ir.actions.act_window']._for_xml_id('custom_master_catalog.action_x_subservice_product_template_view')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        sale_tax_id = self.env.ref('account.1_tax12')
        ctx = eval(action['context'])
        ctx.update({
            'default_uom_id': service_uom_id.id,
            'default_taxes_id': [sale_tax_id.id],
        })
        action.update({'domain': self.get_subservices_domain(), 'context': ctx})
        return action

    # ==== Public Helper, to get product domain ====== #
    def get_subservices_domain(self, categ_id=None):
        all_categ_id = self.env.ref('product.product_category_all')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        sale_tax_id = self.env.ref('account.1_tax12')
        domain = [
            ('sale_ok', '=', True),
            ('sh_product_subscribe', '=', True),
            ('purchase_ok', '=', False),
            ('x_accessory_ok', '=', False),
            ('type', '=', 'service'),
            ('list_price', '=', 1),
            ('standard_price', '=', 0),
            ('taxes_id', 'in', [sale_tax_id.id]),
            ('uom_id', '=', service_uom_id.id),
        ]
        if categ_id is None:  # Si no se pasa una categoría, se busca en todas, diferentes de All
            domain.append(('categ_id', '<>', all_categ_id.id))
        else:  # Si se pasa una categoría, se busca en esa
            domain.append(('categ_id', '=', categ_id.id))
        return domain
