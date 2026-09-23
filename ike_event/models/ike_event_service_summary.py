# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _


class IkeEventServiceSummary(models.Model):
    _name = 'ike.event.service.summary'
    _description = 'Event Service Summary'
    _auto = False

    # === FIELDS === #
    name = fields.Char('Expedient')
    user_id = fields.Many2one('custom.nus')
    user_membership_id = fields.Many2one('custom.membership.nus', 'Membership')
    user_membership_plan_id = fields.Many2one('custom.membership.plan')
    service_id = fields.Many2one('product.category')
    sub_service_id = fields.Many2one('product.product', string='Subservice')
    event_date = fields.Datetime(readonly=True)
    stage_id = fields.Many2one('ike.event.stage')
    event_service_detail_count_id = fields.Many2one('ike.event.service.count.detail')
    suppliers_ids = fields.Many2many('res.partner', string='Suppliers', compute='_compute_suppliers')
    stage_ref = fields.Char(related='stage_id.ref', string='Stage Reference')

    @api.depends()
    def _compute_suppliers(self):
        SupplierLine = self.env['ike.event.supplier']

        for rec in self:
            if not rec.id:
                rec.suppliers_ids = False
                continue

            lines = SupplierLine.search([
                ('event_id', '=', rec.id),
                ('stage_id.ref', '=', 'assigned')
            ]).mapped('supplier_id')

            rec.suppliers_ids = lines

    def init(self):
        """Initialize the SQL view"""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    ie.id AS id,
                    ie.name AS name,
                    ie.user_id AS user_id,
                    ie.user_membership_id AS user_membership_id,
                    cmn.membership_plan_id AS user_membership_plan_id,
                    ie.service_id AS service_id,
                    ie.sub_service_id AS sub_service_id,
                    ie.event_date AS event_date,
                    ie.stage_id AS stage_id
                FROM
                    ike_event ie
                    LEFT JOIN custom_membership_nus cmn ON ie.user_membership_id = cmn.id
                ORDER BY
                    ie.event_date DESC
            )
        """ % (self._table,))
