# -*- coding: utf-8 -*-

# import re

from odoo import models, fields, api, _  # tools
from odoo.exceptions import UserError
from markupsafe import Markup


class CustomSupplierCoverageConfiguration(models.Model):
    _name = 'custom.supplier.coverage.configuration'
    _description = 'Supplier Coverage Configuration'
    _inherit = ['mail.thread']
    _rec_name = 'supplier_id'

    name = fields.Char(default="")
    supplier_id = fields.Many2one(
        'res.partner', string='Supplier', domain=[('x_is_supplier', '=', True)], ondelete='restrict', tracking=True)
    vat = fields.Char(related="supplier_id.vat", string='Vat')
    x_is_electronic = fields.Boolean(related="supplier_id.x_is_electronic", string='Electronics', store=True)
    x_is_manual = fields.Boolean(related="supplier_id.x_is_manual", string='Manual', store=True)
    x_is_extraordinary = fields.Boolean(related="supplier_id.x_is_extraordinary", string='Extraordinary', store=True)

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

    street = fields.Char(related="supplier_id.street")
    street2 = fields.Char(related="supplier_id.street2")
    zip = fields.Char(related="supplier_id.zip", change_default=True)
    city = fields.Char(related="supplier_id.city")
    state_id = fields.Many2one(related="supplier_id.state_id", string='State', ondelete='restrict', domain="[('country_id', '=?', country_id)]")
    country_id = fields.Many2one(related="supplier_id.country_id", string='Country', ondelete='restrict')
    email = fields.Char(related="supplier_id.email")
    phone = fields.Char(related="supplier_id.phone")
    mobile = fields.Char(related="supplier_id.mobile")
    accept_cancellations = fields.Boolean(string='Accept cancellations', default=False, tracking=True)
    waiting_time = fields.Integer(string='Waiting time', default=0, tracking=True)

    supplier_coverage_config_line_ids = fields.One2many(
        'custom.supplier.coverage.configuration.line', 'supplier_coverage_config_id',
        string='Supplier Coverage Configuration Line', tracking=True)

    services_ids = fields.Many2many(
        'product.category',
        'custom_supplier_coverage_config_service_rel',
        'custom_supplier_coverage_config_id',
        'service_id',
        compute='_compute_services_subservices',
        string='Services',
        store=True)
    subservices_ids = fields.Many2many(
        'product.product',
        'custom_supplier_coverage_config_subservice_rel',
        'custom_supplier_coverage_config_id',
        'product_id',
        compute='_compute_services_subservices',
        string='Subservices',
        store=True)

    @api.constrains('supplier_id')
    def _check_unique_supplier(self):
        for rec in self:
            domain = [('supplier_id', '=', rec.supplier_id.id), ('id', '<>', rec.id)]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise UserError(_('The supplier must be unique'))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise UserError(_('The supplier must be unique. It is disabled.'))

    @api.depends('supplier_coverage_config_line_ids.service_id', 'supplier_coverage_config_line_ids.product_id')
    def _compute_services_subservices(self):
        for rec in self:
            rec.services_ids = rec.supplier_coverage_config_line_ids.mapped('service_id')
            rec.subservices_ids = rec.supplier_coverage_config_line_ids.mapped('product_id')

    @api.onchange('accept_cancellations')
    def onchange_accept_cancellations(self):
        if self.accept_cancellations is False:
            self.waiting_time = 0

    @api.model
    def get_can_be_disabled(self):
        """ Inherit and override to restrict disabling capabilities based on specific user groups. """
        res = super().get_can_be_disabled()
        # List of allowed technical group XML IDs
        allowed_groups = [
            'base.group_system',
            'custom_master_catalog.custom_group_supplier_admin_system',
        ]
        has_permission = any(self.env.user.has_group(group) for group in allowed_groups)
        if not has_permission:
            return False
        return res

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


class CustomSupplierCoverageConfigurationLine(models.Model):
    _name = 'custom.supplier.coverage.configuration.line'
    _description = 'Supplier Coverage Configuration Line'
    _rec_name = 'product_id'
    _parent_name = 'supplier_coverage_config_id'

    supplier_coverage_config_id = fields.Many2one(
        "custom.supplier.coverage.configuration", string='Supplier coverage configuration', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', related="supplier_coverage_config_id.supplier_id", store=True)
    service_id = fields.Many2one('product.category', string='Service', sub_tracking=True)
    product_id = fields.Many2one('product.product', string='Subservice', sub_tracking=True)
    x_service_domain = fields.Binary(string="Service domain", compute="_compute_x_service_domain")
    product_domain = fields.Binary(string="Product domain", compute="_compute_product_domain")
    disabled = fields.Boolean(default=False, sub_tracking=True)

    # === COMPUTE METHODS === #
    @api.depends('service_id')
    def _compute_x_service_domain(self):
        for rec in self:
            domain = []

            all_service_id = self.env.ref('product.product_category_all')
            saleable_service_id = self.env.ref('product.product_category_1')
            expense_service_id = self.env.ref('product.cat_expense')

            domain = [
                ('disabled', '=', False),
                ('id', 'not in', [all_service_id.id, saleable_service_id.id, expense_service_id.id])
            ]

            rec.x_service_domain = domain

    @api.depends('service_id', 'supplier_coverage_config_id.supplier_coverage_config_line_ids.product_id')
    def _compute_product_domain(self):
        for rec in self:
            subservice_ids = rec.supplier_coverage_config_id.supplier_coverage_config_line_ids.filtered(
                lambda x: x.id != rec.id
            ).mapped('product_id').ids

            domain = [
                ('type', '=', 'service'),
                ('disabled', '=', False),
                ('id', 'not in', subservice_ids),
            ]

            if rec.service_id:
                domain.append(('categ_id', '=', rec.service_id.id))

            rec.product_domain = domain

    def action_open_geographic_subservice_wizard(self):
        self.ensure_one()

        self.env['custom.geographic.subservice.wizard'].search([]).unlink()

        sql = """
            SELECT
                area.partner_id,
                area.state_id,
                area.municipality_id
            FROM
                custom_supplier_coverage_configuration_line line
            JOIN
                res_partner partner_line ON line.partner_id = partner_line.id
            JOIN
                custom_geographical_area area ON area.parent_id = line.partner_id
            JOIN
                custom_geographical_area_product_rel area_product ON area.id = area_product.geographical_area_id
            WHERE
                line.product_id = area_product.product_id
            AND
                partner_line.parent_id IS NOT NULL
            AND
                line.id = %s
        """
        self.env.cr.execute(sql, (self.id,))
        rows = self.env.cr.fetchall()
        wizard_model = self.env['custom.geographic.subservice.wizard']
        records = []
        for partner_id, state_id, municipality_id in rows:
            record = wizard_model.create({
                'partner_id': partner_id,
                'state_id': state_id,
                'municipality_id': municipality_id,
            })
            records.append(record.id)

        return {
            'name': 'Cobertura geográfica',
            'type': 'ir.actions.act_window',
            'res_model': 'custom.geographic.subservice.wizard',
            'view_mode': 'list',
            'views': [(False, 'list')],
            'target': 'new',
            'domain': [('id', 'in', records)],
            'context': dict(self.env.context),
        }

    def action_disable_line(self):
        self.ensure_one()
        self.supplier_coverage_config_id.write({
            'supplier_coverage_config_line_ids': [(1, self.id, {'disabled': True})]
        })
        self._geographical_area_subservice_disabled(True)

    def action_enable_line(self):
        self.ensure_one()
        self.supplier_coverage_config_id.write({
            'supplier_coverage_config_line_ids': [(1, self.id, {'disabled': False})]
        })
        self._geographical_area_subservice_disabled(False)

    def _geographical_area_subservice_disabled(self, disabled):
        self.env['custom.geographical.area.product.rel'].search([
            ('product_id', '=', self.product_id.id),
            ('geographical_area_id.parent_id', '=', self.partner_id.id),
            ('geographical_area_id.active', '=', True),
        ]).write({'disabled': disabled})