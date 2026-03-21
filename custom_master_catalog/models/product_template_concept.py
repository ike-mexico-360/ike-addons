# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_concept_description = fields.Char(string="Concept description", tracking=True, size=250)
    x_apply_all_services_subservices = fields.Boolean(string="Apply all services subservices", tracking=True)
    x_is_cancelation = fields.Boolean(string="Is cancelation?", tracking=True)
    x_categ_id = fields.Many2one('product.category', string="Service", tracking=True)
    x_product_id = fields.Many2one('product.product', string="Subservice", tracking=True)


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_concept_description = fields.Char(string="Concept description", tracking=True, size=250)
    x_apply_all_services_subservices = fields.Boolean(string="Apply all services subservices", tracking=True)
    x_is_cancelation = fields.Boolean(string="Is cancelation?", tracking=True)
    x_categ_id = fields.Many2one('product.category', string="Service", tracking=True)
    x_product_id = fields.Many2one('product.product', string="Subservice", tracking=True)
    x_product_concept_domain = fields.Binary(string="Concept domain", compute="_compute_x_product_concept_domain")
    x_concepts_uom_domain = fields.Binary(string="UoM domain", compute="_compute_x_concepts_uom_domain")
    x_concepts_categ_domain = fields.Binary(string="Category domain", compute="_compute_x_concepts_categ_domain")

    @api.constrains(
        'name', 'sale_ok', 'sh_product_subscribe', 'purchase_ok', 'x_accessory_ok', 'categ_id', 'uom_id',
        'x_apply_all_services_subservices')
    def chec_unique_concept(self):
        for rec in self:
            domain = rec.get_concepts_domain()
            if self.search_count(domain + [('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', False)]) > 0:
                raise ValidationError(_('A record with the same name already exists.'))
            elif self.search_count(domain + [('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', True)]) > 0:
                raise ValidationError(_('A record with the same name already exists. It is disabled.'))

    @api.depends('uom_id')
    def _compute_x_concepts_uom_domain(self):
        for rec in self:
            domain = []
            if self._context.get('x_concepts_view', False):
                uom_ids = self._get_concepts_uom_ids()
                domain = [('id', 'in', uom_ids)]
            rec.x_concepts_uom_domain = domain

    @api.depends('name')
    def _compute_x_concepts_categ_domain(self):
        for rec in self:
            domain = []
            if self._context.get('x_concepts_view', False):
                all_categ_id = self.env.ref('product.product_category_all')
                domain = [('disabled', '=', False), ('id', 'not in', [all_categ_id.id])]
            rec.x_concepts_categ_domain = domain

    @api.depends('x_categ_id')
    def _compute_x_product_concept_domain(self):
        for rec in self:
            domain = []
            if self._context.get('x_concepts_view', False) and rec.x_categ_id:
                domain = rec.get_subservices_domain(categ_id=rec.x_categ_id)
                domain.append(('disabled', '=', False))
            rec.x_product_concept_domain = domain

    @api.onchange('x_apply_all_services_subservices')
    def onchange_x_apply_all_services_subservices(self):
        if self.x_apply_all_services_subservices:
            self.x_product_id = False
            self.x_categ_id = False

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            if self._context.get('x_concepts_view', False):
                map_vals = []
                # Si aplica a todos, ligar todos
                if rec.x_apply_all_services_subservices:
                    subservice_ids = self.env['product.product'].search(self.get_subservices_domain())
                    map_vals = [{'parent_id': rec.id, 'product_id': x.id} for x in subservice_ids]
                # Si no aplica a todos y tiene categoría, ligar los de la categoría
                elif rec.x_apply_all_services_subservices is False and rec.x_categ_id and not rec.x_product_id:
                    subservice_ids = self.env['product.product'].search(self.get_subservices_domain(categ_id=rec.x_categ_id))
                    map_vals = [{'parent_id': rec.id, 'product_id': x.id} for x in subservice_ids]
                # Se asume que no aplica a todos y tiene categoría y producto, solo ligar el producto
                else:
                    map_vals = [{'parent_id': rec.id, 'product_id': rec.x_product_id.id}]
                if map_vals:
                    self.env['custom.product.mapping'].create(map_vals)
        return res

    def write(self, vals):
        for rec in self:
            if self._context.get('x_concepts_view', False):
                apply_all = vals.get('x_apply_all_services_subservices', False)
                # Si cambia de aplicar para todos, a aplicar a solo algunos, desactivar los que no
                if rec.x_apply_all_services_subservices is True and apply_all is False:
                    set_active_false = self.env['custom.product.mapping']
                    categ_id = vals.get('x_categ_id', False)
                    product_id = vals.get('x_product_id', False)
                    for mapping in rec.x_mapping_ids:
                        if product_id:
                            if mapping.product_id.id != product_id:
                                set_active_false += mapping
                        else:
                            if mapping.product_id.categ_id.id != categ_id:
                                set_active_false += mapping
                    if set_active_false:
                        set_active_false.write({'active': False})
                # Si cambia de aplicar solo a algunos a aplicar a más
                if rec.x_apply_all_services_subservices is False and apply_all is True:
                    set_active_true = self.env['custom.product.mapping'].search([('parent_id', '=', rec.id), ('active', '=', False)])
                    if set_active_true:
                        set_active_true.write({'active': True})
                    domain = self.get_subservices_domain()
                    domain.append(('id', 'not in', set_active_true.mapped('product_id')))
                    subservice_ids = self.env['product.product'].search(domain)
                    map_vals = [{'parent_id': rec.id, 'product_id': x.id} for x in subservice_ids]
                    if map_vals:
                        self.env['custom.product.mapping'].create(map_vals)
        return super().write(vals)

    def get_concepts_view_action(self):
        action = self.env['ir.actions.act_window']._for_xml_id('custom_master_catalog.custom_ike_concepts_product_view_action')
        all_categ_id = self.env.ref('product.product_category_all')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        sale_tax_id = self.env.ref('account.1_tax12')
        ctx = eval(action['context'])
        ctx.update({
            'default_categ_id': all_categ_id.id,
            'default_uom_id': service_uom_id.id,
            'default_taxes_id': [sale_tax_id.id],
        })
        action.update({'domain': self.get_concepts_domain(), 'context': ctx})
        return action

    def get_concepts_domain(self):
        all_categ_id = self.env.ref('product.product_category_all')
        uom_ids = self._get_concepts_uom_ids()
        sale_tax_id = self.env.ref('account.1_tax12')
        return [
            ('sale_ok', '=', False),
            ('sh_product_subscribe', '=', False),
            ('purchase_ok', '=', True),
            ('x_accessory_ok', '=', False),
            ('type', '=', 'service'),
            ('list_price', '=', 0),
            ('standard_price', '=', 0),
            ('categ_id', '=', all_categ_id.id),
            ('uom_id', 'in', uom_ids),
            ('taxes_id', 'in', [sale_tax_id.id]),
        ]

    def _get_concepts_uom_ids(self):
        return [
            self.env.ref('uom.product_uom_km').id,  # KM
            self.env.ref('uom.product_uom_day').id,  # Day
            self.env.ref('l10n_mx.product_uom_service_unit').id,  # Service
            self.env.ref('uom.product_uom_unit').id,  # Unit
            self.env.ref('uom.product_uom_litre').id,  # Litre
        ]
