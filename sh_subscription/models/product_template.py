# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import api, fields, models
from odoo.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = "product.template"

    sh_product_subscribe = fields.Boolean(
        string="Is Subscription Type",
        help="Click false to hide.",
        compute="_compute_sh_product_subscribe",
        inverse="_set_sh_product_subscribe",
        store=True,
        search="_search_sh_product_subscribe",
    )
    sh_subscription_plan_id = fields.Many2one(
        comodel_name="sh.subscription.plan",
        string="Subscription Plan",
        compute="_compute_sh_subscription_plan_id",
        inverse="_set_sh_subscription_plan_id",
        store=True,
        search="_search_sh_subscription_plan_id",
    )
    x_subscription_plan_ids = fields.Many2many(
        comodel_name='sh.subscription.plan',
        relation='product_template_subscription_plan',
        column1='product_template_id',
        column2='subscription_plan_id',
        compute="_compute_x_subscription_plan_ids",
        inverse="_set_x_subscription_plan_ids",
        store=True,
        string='Planes de afiliación')

    """ # Código comentado por error al validar variantes de productos cuando no se usan variantes
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Check if product is subscription type and validate attributes
            if vals.get("sh_product_subscribe") and "attribute_line_ids" in vals:
                attribute_line_ids = vals["attribute_line_ids"]

                if len(attribute_line_ids) > 1:
                    raise UserError(
                        "You can't take more than one attribute in the subscription type product."
                    )

                subscription_attribute = self.env.ref("sh_subscription.product_attribute_subscription")
                if not any(att[2]["attribute_id"] == subscription_attribute.id for att in attribute_line_ids):
                    raise UserError(
                        "You must select the subscription attribute in the subscription type product."
                    )
        return super(ProductTemplate, self).create(vals_list)

    def write(self, vals):
        if vals.get("sh_product_subscribe") and "attribute_line_ids" in vals:
            attribute_line_ids = vals["attribute_line_ids"]

            if len(attribute_line_ids) > 1:
                raise UserError(
                    "You can't take more than one attribute in the subscription type product."
                )

            subscription_attribute = self.env.ref("sh_subscription.product_attribute_subscription")
            if not any(att[2]["attribute_id"] == subscription_attribute.id for att in attribute_line_ids):
                raise UserError(
                    "You must select the subscription attribute in the subscription type product."
                )

        return super(ProductTemplate, self).write(vals)
    """

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

    @api.depends("product_variant_ids.sh_subscription_plan_id")
    def _compute_sh_subscription_plan_id(self):
        """Compute the subscription plan based on the first product variant."""
        for template in self:
            template.sh_subscription_plan_id = (
                len(template.product_variant_ids) == 1 and template.product_variant_ids.sh_subscription_plan_id.id
            )

    def _search_sh_subscription_plan_id(self, operator, value):
        """Search for templates based on the subscription plan."""
        templates = self.with_context(active_test=False).search(
            [("product_variant_ids.sh_subscription_plan_id", operator, value)]
        )
        return [("id", "in", templates.ids)]

    def _set_sh_subscription_plan_id(self):
        """Set the subscription plan on product variants."""
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.sh_subscription_plan_id = self.sh_subscription_plan_id.id

    @api.depends("product_variant_ids.x_subscription_plan_ids")
    def _compute_x_subscription_plan_ids(self):
        """Compute the subscription plan based on the first product variant."""
        for template in self:
            template.x_subscription_plan_ids = (
                len(template.product_variant_ids) == 1 and template.product_variant_ids.x_subscription_plan_ids.ids
            )

    def _search_x_subscription_plan_ids(self, operator, value):
        """Search for templates based on the subscription plan."""
        templates = self.with_context(active_test=False).search(
            [("product_variant_ids.x_subscription_plan_ids", operator, value)]
        )
        return [("id", "in", templates.ids)]

    def _set_x_subscription_plan_ids(self):
        """Set the subscription plan on product variants."""
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.x_subscription_plan_ids = self.x_subscription_plan_ids.ids

    @api.onchange("sh_product_subscribe")
    def _onchange_sh_product_subscribe(self):
        """Set product type to 'service' if it is a subscription."""
        if self.sh_product_subscribe:
            self.type = "service"

    @api.onchange("sh_subscription_plan_id")
    def _onchange_sh_subscription_plan_id_product(self):
        """Update the product price if the subscription plan overrides the product price."""
        if self.sh_subscription_plan_id and self.sh_subscription_plan_id.sh_override_product:
            self.list_price = self.sh_subscription_plan_id.sh_plan_price

    def write(self, vals):
        old_plans_aux = []
        if 'x_subscription_plan_ids' in vals:
            for template in self:
                old_plans_aux.append({"template": template, "subscription_plan_ids": template.x_subscription_plan_ids.ids})
        res = super().write(vals)
        if 'x_subscription_plan_ids' in vals and not self.env.context.get('from_sh_subscription_plan'):
            for template in self:
                # Obtener los planes actuales y nuevos para comparar
                new_plans = set(template.x_subscription_plan_ids.ids)
                # Obtener los planes "antiguos"
                old_plans = {}
                for op in old_plans_aux:
                    if op.get("template") == template:
                        old_plans = set(op.get("subscription_plan_ids"))
                # Planes que se agregaron
                aggregate_plans = new_plans - old_plans
                # Planes que se quitaron
                plans_removed = old_plans - new_plans
                # Por cada plan agregado, agregar línea en x_product_line_ids de ese plan
                for plan_id in aggregate_plans:
                    plan = self.env['sh.subscription.plan'].browse(plan_id)
                    # Crear línea si no existe aún
                    if not plan.x_product_line_ids.filtered(lambda x: x.x_product_id.product_tmpl_id.id == template.id):
                        self.env['x_sh.subscription.plan.line'].create({
                            'x_subscription_plan_id': plan.id,
                            'x_product_id': template.product_variant_ids[0].id,
                        })
                # Por cada plan quitado, eliminar la línea correspondiente
                for plan_id in plans_removed:
                    plan = self.env['sh.subscription.plan'].browse(plan_id)
                    lineas = plan.x_product_line_ids.filtered(lambda x: x.x_product_id.product_tmpl_id.id == template.id)
                    if lineas:
                        lineas.unlink()
        return res


class Product(models.Model):
    _inherit = "product.product"

    sh_product_subscribe = fields.Boolean(
        string="Is Subscription Type", help="Click false to hide."
    )
    sh_subscription_plan_id = fields.Many2one(
        comodel_name="sh.subscription.plan", string="Subscription Plan"
    )
    x_subscription_plan_ids = fields.Many2many(
        'sh.subscription.plan', 'product_product_subscription_plan_rel', 'product_id',
        'subscription_plan_id', 'Planes de afiliación')

    @api.onchange("sh_product_subscribe")
    def _onchange_sh_product_subscribe(self):
        """Set product type to 'service' if it is a subscription."""
        if self.sh_product_subscribe:
            self.type = "service"

    @api.onchange("sh_subscription_plan_id")
    def _onchange_sh_subscription_plan_id_product(self):
        """Update the price extra of subscription attribute based on the selected plan."""
        if self.sh_subscription_plan_id and self.sh_subscription_plan_id.sh_override_product:
            subscription_attribute = self.env.ref("sh_subscription.product_attribute_subscription")
            if subscription_attribute:
                variant_value = self.product_template_variant_value_ids.filtered(
                    lambda x: x.attribute_id == subscription_attribute
                )
                if variant_value:
                    variant_value[0]._origin.price_extra = self.sh_subscription_plan_id.sh_plan_price

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            template_id = self.env["product.template"].sudo().browse(vals.get("product_tmpl_id"))
            if template_id:
                vals.update(
                    {
                        "sh_product_subscribe": template_id.sh_product_subscribe,
                        # "sh_subscription_plan_id": template_id.sh_subscription_plan_id.id,
                        "x_subscription_plan_ids": template_id.x_subscription_plan_ids.ids,
                    }
                )
        return super(Product, self).create(vals_list)
