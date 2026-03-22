# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_concept_description = fields.Char(string="Concept description", tracking=True, size=250)
    x_apply_all_services_subservices = fields.Boolean(string="Apply all services subservices", tracking=True)
    x_is_cancelation = fields.Boolean(string="Is cancelation?", tracking=True)
    x_categ_id = fields.Many2one('product.category', string="Service", tracking=True)
    x_product_id = fields.Many2one('product.product', string="Subservice", tracking=True)

    x_concept_ok = fields.Boolean(
        string="Concept", compute='_compute_x_concept_ok', inverse='_set_x_concept_ok',
        search='_search_x_concept_ok')

    @api.depends('product_variant_ids.x_concept_ok')
    def _compute_x_concept_ok(self):
        self._compute_template_field_from_variant_field('x_concept_ok')

    def _set_x_concept_ok(self):
        self._set_product_variant_field('x_concept_ok')

    def _search_x_concept_ok(self, operator, value):
        return [('product_variant_ids.x_concept_ok', operator, value)]


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_concept_description = fields.Char(string="Concept description", tracking=True, size=250)
    x_apply_all_services_subservices = fields.Boolean(string="Apply all services subservices", tracking=True)
    x_is_cancelation = fields.Boolean(string="Is cancelation?", tracking=True)
    x_categ_id = fields.Many2one('product.category', string="Service", tracking=True)
    x_product_id = fields.Many2one('product.product', string="Subservice", tracking=True)
    x_product_concept_domain = fields.Binary(string="Concept domain", compute="_compute_x_product_concept_domain")
    x_concepts_uom_domain = fields.Binary(string="UoM domain", compute="_compute_x_concepts_uom_domain")
    x_concepts_categ_domain = fields.Binary(string="Concept category domain", compute="_compute_x_concepts_categ_domain")
    x_min_required_photos = fields.Integer(
        string="Minimum Required Photos",
        default=0,
        help="Evidence photos required for this subservice."
    )
    x_concept_ok = fields.Boolean(string="Concept", tracking=True)
    x_additional_ok = fields.Boolean(string="Is additional", tracking=True)

    @api.constrains(
        'name', 'sale_ok', 'sh_product_subscribe', 'purchase_ok', 'x_concept_ok', 'categ_id', 'uom_id',
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
                saleable_categ_id = self.env.ref('product.product_category_1')
                expense_categ_id = self.env.ref('product.cat_expense')
                domain = [('disabled', '=', False), ('id', 'not in', [all_categ_id.id, saleable_categ_id.id, expense_categ_id.id])]
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

    @api.onchange('x_categ_id')
    def onchange_x_categ_id(self):
        self.x_product_id = False

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            if self._context.get('x_concepts_view', False):
                map_vals = []
                # Si aplica a todos, ligar todos
                if rec.x_apply_all_services_subservices:
                    subservice_ids = self.env['product.product'].search(self.get_subservices_domain() + [('disabled', '=', False)])
                    map_vals = [{'parent_id': rec.id, 'product_id': x.id} for x in subservice_ids]
                # Si no aplica a todos y tiene categoría, ligar los de la categoría
                elif rec.x_apply_all_services_subservices is False and rec.x_categ_id and not rec.x_product_id:
                    subservice_ids = self.env['product.product'].search(self.get_subservices_domain(categ_id=rec.x_categ_id) + [('disabled', '=', False)])
                    map_vals = [{'parent_id': rec.id, 'product_id': x.id} for x in subservice_ids]
                # Se asume que no aplica a todos y tiene categoría y producto, solo ligar el producto
                else:
                    map_vals = [{'parent_id': rec.id, 'product_id': rec.x_product_id.id}]
                if map_vals:
                    self.env['custom.product.mapping'].create(map_vals)
        return res

    def write(self, vals):
        def _assign_all_subservices(rec, new_apply_all):
            exist_in_mappings = rec.with_context(active_test=False).x_mapping_ids.filtered(
                lambda x: x.active is False or x.active is True)
            exist_in_mappings.with_context(active_test=False).filtered(lambda x: x.active is False).write({'active': True})
            # Realizamos búsqueda de los subservicios de ese servicio, excluyendo los existentes
            domain = self.get_subservices_domain()
            domain.append(('id', 'not in', exist_in_mappings.mapped('product_id').ids))
            # Si hay subservicios faltantes, los creamos
            new_subservice_ids = self.env['product.product'].search(domain + [('disabled', '=', False)])
            map_vals = [{'parent_id': rec.id, 'product_id': x.id} for x in new_subservice_ids]
            if map_vals:
                self.env['custom.product.mapping'].create(map_vals)

        def _assign_new_subservice(rec, new_subservice):
            # Buscamos si ese subservicio ya existe en la lista de mapeos
            exist_in_mappings = rec.with_context(active_test=False).x_mapping_ids.filtered(
                lambda x: x.product_id.id == new_subservice)
            # Si existe, solo desactivaremos los demás a excepción de ese
            if exist_in_mappings:
                rec.with_context(active_test=False).x_mapping_ids.filtered(
                    lambda x: x.active is True and x.product_id.id != new_subservice
                ).write({'active': False})
                if exist_in_mappings.active is False:
                    exist_in_mappings.write({'active': True})
            # Si no existe, desactivamos todos los demás y creamos el nuevo
            else:
                rec.with_context(active_test=False).x_mapping_ids.filtered(lambda x: x.active is True).write({'active': False})
                map_vals = [{'parent_id': rec.id, 'product_id': new_subservice}]
                self.env['custom.product.mapping'].create(map_vals)

        def _assign_all_subservices_of_service(rec, new_service=False):
            # Por si llegara a haber subservicios que no son de la categoría, los desactivaremos
            service_id = new_service if new_service else rec.x_categ_id.id
            # Obtenemos los subservicios de esa categoría que existen en el campo de mapeo
            exist_in_mappings = rec.with_context(active_test=False).x_mapping_ids.filtered(
                lambda x: x.categ_id.id == service_id and (x.active is False or x.active is True))
            exist_in_mappings.with_context(active_test=False).filtered(lambda x: x.active is False).write({'active': True})
            rec.with_context(active_test=False).x_mapping_ids.filtered(
                lambda x: x.active is True and x.categ_id.id != service_id
            ).write({'active': False})
            # Realizamos búsqueda de los subservicios de ese servicio, excluyendo los existentes
            domain = self.get_subservices_domain()
            domain.append(('id', 'not in', exist_in_mappings.mapped('product_id').ids))
            domain.append(('categ_id', '=', service_id))
            # Si hay subservicios faltantes, los creamos
            new_subservice_ids = self.env['product.product'].search(domain + [('disabled', '=', False)])
            map_vals = [{'parent_id': rec.id, 'product_id': x.id} for x in new_subservice_ids]
            if map_vals:
                self.env['custom.product.mapping'].create(map_vals)

        for rec in self:
            # ToDo: Refactorizar para reducir código, hay escenarios que se pueden fusionar
            if self._context.get('x_concepts_view', False):
                new_apply_all = vals.get('x_apply_all_services_subservices', False)
                new_service = vals.get('x_categ_id', False)
                new_subservice = vals.get('x_product_id', False)

                change_apply_all = rec.x_apply_all_services_subservices != new_apply_all
                change_service = rec.x_categ_id.id != new_service
                change_subservice = rec.x_product_id.id != new_subservice

                if change_apply_all or change_service or change_subservice:
                    # * Cambia a que si aplica a todos teniendo valor servicio y subservicio
                    # * Si cambia a que no aplica a todos y se establecen servicio y subservicio
                    if change_apply_all and change_service and change_subservice:
                        if new_apply_all is True:
                            _assign_all_subservices(rec, new_apply_all)
                        else:
                            if new_service:
                                _assign_new_subservice(rec, new_subservice)
                            else:
                                _assign_all_subservices_of_service(rec, new_service=new_service)

                    # * Si cambia que no aplica a todos y se establece solo servicio
                    # * Si cambia a que aplica a todos y solo está establecido servicio
                    if change_apply_all and change_service and not change_subservice:
                        if new_apply_all is True:
                            _assign_all_subservices(rec, new_apply_all)
                        else:
                            _assign_all_subservices_of_service(rec, new_service=new_service)

                    # * Solo cambia el servicio
                    if not change_apply_all and change_service and not change_subservice:
                        if new_subservice:
                            _assign_new_subservice(rec, new_subservice)
                        else:
                            _assign_all_subservices_of_service(rec, new_service=new_service)

                    # * Cambia el subservicio
                    if not change_apply_all and change_service and change_subservice:
                        if new_subservice:
                            _assign_new_subservice(rec, new_subservice)
                        else:
                            _assign_all_subservices_of_service(rec, new_service=new_service)

        return super().write(vals)

    def get_concepts_view_action(self):
        action = self.env['ir.actions.act_window']._for_xml_id('custom_master_catalog.custom_ike_concepts_product_view_action')
        all_categ_id = self.env.ref('product.product_category_all')
        service_uom_id = self.env.ref('l10n_mx.product_uom_service_unit')
        ctx = eval(action['context'])
        ctx.update({
            'default_categ_id': all_categ_id.id,
            'default_uom_id': service_uom_id.id,
        })
        action.update({'domain': self.get_concepts_domain(), 'context': ctx})
        return action

    @api.model
    def get_concepts_domain(self):
        all_categ_id = self.env.ref('product.product_category_all')
        uom_ids = self._get_concepts_uom_ids()
        return [
            ('sale_ok', '=', False),
            ('sh_product_subscribe', '=', False),
            ('purchase_ok', '=', True),
            ('x_concept_ok', '=', True),
            ('type', '=', 'service'),
            ('list_price', '=', 0),
            ('categ_id', '=', all_categ_id.id),
            ('uom_id', 'in', uom_ids),
        ]

    def _get_concepts_uom_ids(self):
        return [
            self.env.ref('uom.product_uom_km').id,  # KM
            self.env.ref('uom.product_uom_day').id,  # Day
            self.env.ref('uom.product_uom_hour').id,  # Hour
            self.env.ref('l10n_mx.product_uom_service_unit').id,  # Service
            self.env.ref('uom.product_uom_unit').id,  # Unit
            self.env.ref('uom.product_uom_litre').id,  # Litre
        ]

    # Heredamos el método _creation_message para modificar el mensaje de creación
    def _creation_message(self):
        self.ensure_one()
        if self.env.context.get('x_concepts_view'):
            return _("Concept created")
        return super()._creation_message()
