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
    x_categ_domain = fields.Binary(string="Category domain", compute="_compute_x_categ_domain")
    x_concepts_ids = fields.Many2many(
        'product.product',
        'subservice_concept_rel',
        'subservice_id',
        'concept_id',
        string='Concepts')
    x_concepts_domain = fields.Binary(string="Concept domain ", compute="_compute_x_concepts_domain")
    concept_line_ids = fields.One2many(
        'custom.subservice.concept.line', 'subservice_id',
        string='Concept line')
    x_min_required_photos_assistview = fields.Integer(
        string="Minimum Required Photos (Assistview)",
        default=0,
        help="Evidence photos required for this subservice (Assistview)."
    )
    active = fields.Boolean(readonly=True)

    @api.constrains('name', 'sale_ok', 'sh_product_subscribe', 'purchase_ok', 'x_accessory_ok', 'categ_id', 'uom_id')
    def _check_unique_subservice(self):
        for rec in self:
            domain = rec.get_subservices_domain()
            if self.search_count(domain + [('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', False)]) > 0:
                raise ValidationError(_('A record with the same name already exists.'))
            elif self.search_count(domain + [('id', '<>', rec.id), ('name', '=', rec.name), ('disabled', '=', True)]) > 0:
                raise ValidationError(_('A record with the same name already exists. It is disabled.'))

    @api.depends('x_concepts_ids')
    def _compute_x_concepts_domain(self):
        for rec in self:
            domain = self.get_concepts_domain()
            domain.append(('x_categ_id', 'in', [self.categ_id.id, False]))
            domain.append(('disabled', '=', False))
            rec.x_concepts_domain = domain

    @api.depends('name')
    def _compute_x_categ_domain(self):
        for rec in self:
            domain = []
            if self._context.get('x_subservice_view', False):
                all_categ_id = self.env.ref('product.product_category_all')
                saleable_categ_id = self.env.ref('product.product_category_1')
                expense_categ_id = self.env.ref('product.cat_expense')
                domain = [('disabled', '=', False), ('id', 'not in', [all_categ_id.id, saleable_categ_id.id, expense_categ_id.id])]
            rec.x_categ_domain = domain

    def get_subservices_view_action(self):
        action = self.env['ir.actions.act_window']._for_xml_id('custom_master_catalog.action_x_subservice_product_template_view')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        ctx = eval(action['context'])
        ctx.update({
            'default_uom_id': service_uom_id.id,
        })
        if not self.env.user.has_group('base.group_system'):
            readonly_view = self.env.ref('custom_master_catalog.view_product_product_form_readonly')
            list_readonly_view = self.env.ref('custom_master_catalog.view_x_subservice_product_template_list')
            action['views'] = [(list_readonly_view.id, 'list'), (readonly_view.id, 'form')]
        action.update({'domain': self.get_subservices_domain(), 'context': ctx})
        return action

    # ==== Public Helper, to get product domain ====== #
    def get_subservices_domain(self, categ_id=None):
        all_categ_id = self.env.ref('product.product_category_all')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        domain = [
            ('sale_ok', '=', True),
            ('sh_product_subscribe', '=', True),
            ('purchase_ok', '=', False),
            ('x_accessory_ok', '=', False),
            ('type', '=', 'service'),
            ('list_price', '=', 1),
            ('standard_price', '=', 0),
            ('uom_id', '=', service_uom_id.id),
        ]
        if categ_id is None:  # Si no se pasa una categoría, se busca en todas, diferentes de All
            domain.append(('categ_id', '<>', all_categ_id.id))
        else:  # Si se pasa una categoría, se busca en esa
            domain.append(('categ_id', '=', categ_id.id))
        return domain

    # Heredamos el método _creation_message para modificar el mensaje de creación
    def _creation_message(self):
        self.ensure_one()
        if self.env.context.get('x_subservice_view'):
            return _("Subservice created")
        return super()._creation_message()


class CustomSubserviceConceptLine(models.Model):
    _name = 'custom.subservice.concept.line'

    subservice_id = fields.Many2one(
        'product.product',
        'Subservice',
        domain="[('disabled', '=', False)]"
    )

    categ_id = fields.Many2one('product.category', related="subservice_id.categ_id")
    event_type_id = fields.Many2one(
        'custom.type.event',
        'Event type',
        domain="[('disabled', '=', False)]"
    )
    concepts_ids = fields.Many2many(
        'product.product',
        'subservice_concept_line_concept_rel',
        'subservice_concept_line_id',
        'concept_id',
        string='Concepts')
    base_concept_id = fields.Many2one('product.product', string='Base Concept')
    concepts_domain = fields.Binary(string="Concept domain", compute="_compute_concepts_domain")
    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False)

    @api.depends('concepts_ids')
    def _compute_concepts_domain(self):
        for rec in self:
            domain = self.env['product.product'].get_concepts_domain()
            domain.append(('x_categ_id', 'in', [self.categ_id.id, False]))
            domain.append(('disabled', '=', False))
            rec.concepts_domain = domain
