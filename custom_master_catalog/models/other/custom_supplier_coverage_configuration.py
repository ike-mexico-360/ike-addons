# -*- coding: utf-8 -*-

# import re

from odoo import models, fields, api, _  # tools
# from odoo.exceptions import ValidationError
from markupsafe import Markup


class CustomSupplierCoverageConfiguration(models.Model):
    _name = 'custom.supplier.coverage.configuration'
    _description = 'Supplier Coverage Configuration'
    _inherit = ['mail.thread']
    _rec_name = 'supplier_id'

    name = fields.Char(default="")
    supplier_id = fields.Many2one(
        'res.partner', string='Supplier', domain=[('x_is_supplier', '=', True)], ondelete='restrict', tracking=True)

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

    @api.onchange('accept_cancellations')
    def onchange_accept_cancellations(self):
        if self.accept_cancellations is False:
            self.waiting_time = 0

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
