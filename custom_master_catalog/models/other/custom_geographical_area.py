# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class CustomGeographicalArea(models.Model):
    _name = 'custom.geographical.area'
    _description = 'Geographical Coverage Area'
    _rec_name = 'municipality_id'
    _parent_name = 'partner_id'

    _sql_constraints = [(
        'municipality_uniq',
        'unique(partner_id, municipality_id)',
        'Municipality must be unique per partner.'
    )]

    partner_id = fields.Many2one('res.partner', string='Partner', required=True)
    parent_id = fields.Many2one('res.partner', related="partner_id.parent_id", string='Parent', store=True)

    country_id = fields.Many2one('res.country', required=True, default=lambda self: self.env.ref("base.mx"))
    state_id = fields.Many2one('res.country.state', required=True)
    municipality_id = fields.Many2one('custom.state.municipality', required=True, index=True, sub_tracking=True)

    area_product_ids = fields.One2many(
        'custom.geographical.area.product.rel', 'geographical_area_id',
        string='Sub-Services', sub_tracking=True)

    disabled_reason = fields.Text(string='Disabled Reason', readonly=True, sub_tracking=True)
    disabled = fields.Boolean(default=False, sub_tracking=True)
    active = fields.Boolean(default=True)

    field_char = fields.Char(sub_tracking=True)
    field_float = fields.Float(sub_tracking=True)

    @api.onchange('state_id')
    def _onchange_state_id(self):
        if not self.country_id and self.state_id:
            self.country_id = self.state_id.country_id.id

    @api.onchange('municipality_id')
    def _onchange_municipality_id(self):
        if self.municipality_id:
            if not self.state_id:
                self.state_id = self.municipality_id.state_id.id

    def action_edit(self):
        self.ensure_one()

        supplier_id = self.parent_id or self.partner_id
        allowed_product_ids = []
        if supplier_id:
            allowed_product_ids = supplier_id.x_allowed_product_ids.ids

        return {
            'name': _("Sub-Services"),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'custom.geographical.area',
            'view_id': self.env.ref('custom_master_catalog.custom_geographical_area_view_form').id,
            'res_id': self.id,
            'context': {
                'allowed_product_ids': allowed_product_ids,
                'mail_sub_track': True,
            },
            'target': 'new',
        }

    def action_disable(self, reason=None):
        if reason:
            self.disabled_reason = reason
        return super().action_disable(reason)


class CustomGeographicalAreaProduct(models.Model):
    _name = 'custom.geographical.area.product.rel'
    _description = 'Geographical Area Sub-Service'
    _rec_name = 'product_id'

    _sql_constraints = [(
        'product_uniq',
        'unique(geographical_area_id, product_id)',
        'Sub-Service must be unique per Geographical Area.'
    )]

    geographical_area_id = fields.Many2one(
        'custom.geographical.area', string='Geographical Coverage Area',
        ondelete='cascade',
        required=True)
    product_id = fields.Many2one('product.product', string='Sub-Service', required=True)
    color = fields.Integer()
    product_category_color = fields.Integer(related='product_id.categ_id.x_color', string='Product Color')
    color_computed = fields.Integer(compute='_compute_color_computed', store=True)

    disabled_reason = fields.Text(readonly=True)
    disabled = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    @api.depends('color', 'product_category_color', 'disabled', 'geographical_area_id.disabled')
    def _compute_color_computed(self):
        for rec in self:
            rec.color_computed = (
                (rec.color or rec.product_category_color)
                if not rec.disabled and not rec.geographical_area_id.disabled
                else 12
            )
