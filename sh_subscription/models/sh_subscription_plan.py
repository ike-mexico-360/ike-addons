# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api
from odoo.exceptions import UserError

class SubscriptionPlan(models.Model):
    _name = 'sh.subscription.plan'
    _description = 'Subscription Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Default currency based on the company's currency
    def _get_default_currency_id(self):
        return self.env.company.currency_id.id

    # Basic plan fields
    active = fields.Boolean(string="Active", default=True)
    name = fields.Char(string='Plan Name', required=True)
    company_id = fields.Many2one('res.company', required=True, index=True, default=lambda self: self.env.company)
    
    # Plan details
    sh_duration = fields.Integer(string='Duration', required=True)
    sh_unit = fields.Selection(
        [("day", "Day(s)"), ("week", "Week(s)"), ("month", "Month(s)"), ("year", "Year(s)")],
        required=True, default='day', string="Unit")
    sh_plan_price = fields.Float(string='Price', required=True)
    currency_id = fields.Many2one("res.currency", default=_get_default_currency_id)
    sh_company_id = fields.Many2one('res.company', readonly=True, default=lambda self: self.env.company)
    sh_never_expire = fields.Boolean(string="Never Expire")
    sh_no_of_billing_cycle = fields.Integer(string='No of billing cycle', required=True)
    sh_start_immediately = fields.Boolean(string="Start Immediately")
    sh_billing_day_of_the_month = fields.Integer(string='Billing day of the month', default=1)
    sh_trial = fields.Boolean(string="Plan has trial period")
    sh_trial_duration = fields.Integer(string='Trial duration')
    sh_trial_unit = fields.Selection(
        [("day", "Day(s)"), ("week", "Week(s)"), ("month", "Month(s)"), ("year", "Year(s)")],
        string="Unit")
    sh_free_trial_for_current_month = fields.Boolean(string="Free trial for current month")
    sh_is_close_by_customer = fields.Boolean(string="Is Closable By Customer")
    
    # Product details
    sh_override_product = fields.Boolean(string="Override Product Price")
    sh_description = fields.Text(string="Description")

    # Computed fields for counts
    sh_subscription_count = fields.Integer(string="Subscription", compute='_compute_view_subscription', default=0)
    sh_product_count = fields.Integer(string="Product", compute='_compute_view_product', default=0)
    sh_reminder = fields.Many2many("sh.reminder.template", string="Reminder")
    color = fields.Integer('Color Index', default=0)
    x_partner_id = fields.Many2one(
        comodel_name="res.partner", string="Cuenta", domain="[('x_is_account', '=', True),('is_company', '=', True)]")
    x_product_ids = fields.Many2many(
        comodel_name='product.product',
        relation='product_product_subscription_plan_rel',
        column1='subscription_plan_id',
        column2='product_id',
        domain="[('sale_ok', '=', True),('sh_product_subscribe', '=', True)]",
        compute="_compute_product_ids",
        store=True,
        string='Productos')
    x_product_line_ids = fields.One2many('x_sh.subscription.plan.line', 'x_subscription_plan_id', 'Productos')

    # Reset free trial if the unit is not 'month'
    @api.onchange('sh_unit')
    def _onchange_sh_unit(self):
        if self.sh_unit != 'month':
            self.sh_free_trial_for_current_month = False

    # Ensure billing day of the month is valid if free trial is selected
    @api.constrains('sh_billing_day_of_the_month')
    def _check_sh_billing_day_of_the_month(self):
        if self.sh_free_trial_for_current_month and self.sh_billing_day_of_the_month < 1:
            raise UserError("You cannot select less than 1 as the billing day.")

    # Update product prices based on plan price
    @api.onchange('sh_plan_price')
    def _onchange_sh_plan_price(self):
        if self.sh_plan_price:
            products = self.env['product.product'].search([('sh_subscription_plan_id', '=', self._origin.id)])
            products.write({'lst_price': self.sh_plan_price})

    # Ensure mutually exclusive trial options
    @api.onchange('sh_start_immediately')
    def _onchange_sh_start_immediately(self):
        if self.sh_start_immediately:
            self.sh_trial = self.sh_free_trial_for_current_month = False

    @api.onchange('sh_free_trial_for_current_month')
    def _onchange_sh_free_trial_for_current_month(self):
        if self.sh_free_trial_for_current_month:
            self.sh_trial = self.sh_start_immediately = False

    @api.onchange('sh_trial')
    def _onchange_sh_trial(self):
        if self.sh_trial:
            self.sh_start_immediately = self.sh_free_trial_for_current_month = False

    # Compute number of subscriptions linked to the plan
    def _compute_view_subscription(self):
        for rec in self:
            rec.sh_subscription_count = self.env['sh.subscription.subscription'].search_count(
                [('sh_subscription_plan_id', '=', rec.id)])

    # Action to view subscriptions linked to the plan
    def action_view_subscription(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("sh_subscription.sh_subscription_subscription_action")
        subscription = self.env['sh.subscription.subscription'].search([('sh_subscription_plan_id', '=', self.id)])
        
        if len(subscription) > 1:
            action['domain'] = [('id', 'in', subscription.ids)]
        elif subscription:
            action.update({
                'views': [(self.env.ref('sh_subscription.sh_subscription_subscription_form_view').id, 'form')],
                'res_id': subscription.id
            })
        action['context'] = {'active_test': False, 'create': False}
        return action

    # Compute number of products linked to the plan
    def _compute_view_product(self):
        for rec in self:
            # rec.sh_product_count = self.env['product.product'].search_count(
            #     [('sh_subscription_plan_id', '=', rec.id)])
            rec.sh_product_count = self.env['product.product'].search_count(
                [('x_subscription_plan_ids', 'in', [rec.id])])

    # Action to view products linked to the plan
    def action_view_product(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("product.product_variant_action")
        # product = self.env['product.product'].search([('sh_subscription_plan_id', '=', self.id)])
        product = self.env['product.product'].search([('x_subscription_plan_ids', 'in', [self.id])])

        if len(product) > 1:
            action['domain'] = [('id', 'in', product.ids)]
        elif product:
            action.update({
                'views': [(self.env.ref('product.product_normal_form_view').id, 'form')],
                'res_id': product.id
            })
        action['context'] = {'active_test': False, 'create': False}
        return action

    @api.depends("x_product_line_ids")
    def _compute_product_ids(self):
        for rec in self:
            rec.x_product_ids = rec.x_product_line_ids and rec.x_product_line_ids.mapped("x_product_id").ids or False


class SubscriptionPlanLine(models.Model):
    _name = 'x_sh.subscription.plan.line'
    _description = 'x_sh.subscription.plan.line'
    _order = 'id'

    x_company_id = fields.Many2one("res.company", string="Empresa", readonly=True, default=lambda self: self.env.company)
    x_subscription_plan_id = fields.Many2one("sh.subscription.plan", string="Suscripción")
    x_product_id = fields.Many2one('product.product', 'Producto', domain="[('sh_product_subscribe','=', True)]")
    x_taxes_ids = fields.Many2many("account.tax", string="Impuestos")
    x_date_reset = fields.Date(string='Fecha de Reseteo')
    x_no_of_billing_cycle = fields.Integer(string='Número de ciclos de facturación')
    x_qty = fields.Float(string='Cantidad', default=1)
    x_qty_used = fields.Float(string='Cantidad usada')
    x_qty_remain = fields.Float(string='Cantidad restante')
    x_qty_unlimited = fields.Boolean(string='Cantidad ilimitada')
    x_cl_subscription = fields.Char('CL Cobertura', compute="_compute_x_cl_subscription")

    @api.depends("x_product_id")
    def _compute_x_cl_subscription(self):
        for rec in self:
            x_cl_subscription = ""
            if rec.x_subscription_plan_id.x_partner_id and rec.x_subscription_plan_id.x_partner_id.x_cl_code:
                x_cl_subscription = str(rec.x_subscription_plan_id.x_partner_id.x_cl_code)
            if rec.x_product_id.product_tmpl_id.x_cl_sub_service:
                x_cl_subscription = x_cl_subscription + "-" + str(rec.x_product_id.product_tmpl_id.x_cl_sub_service)
            if rec.x_product_id.categ_id.x_cl_service:
                x_cl_subscription = x_cl_subscription + "-" + str(rec.x_product_id.categ_id.x_cl_service)
            rec.x_cl_subscription = x_cl_subscription

    @api.onchange('x_product_id')
    def _onchange_x_product_id(self):
        self.x_taxes_ids = self.x_product_id.taxes_id.filtered_domain(
            self.env['account.tax']._check_company_domain(self.x_company_id)).ids

    def unlink(self):
        for line in self:
            if line.x_product_id:
                line.x_subscription_plan_id.write({'x_product_ids': [(3, line.x_product_id.id, 0)]})
                if line.x_product_id.product_tmpl_id.x_subscription_plan_ids.filtered(
                    lambda x: x.id == line.x_subscription_plan_id.id
                ):
                    line.x_product_id.product_tmpl_id.with_context(afrom_sh_subscription_plan=True).write(
                        {'x_subscription_plan_ids': [(3, line.x_subscription_plan_id.id, 0)]})
        return super(SubscriptionPlanLine, self).unlink()
