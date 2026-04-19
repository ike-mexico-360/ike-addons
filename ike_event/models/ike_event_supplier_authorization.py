# -*- coding: utf-8 -*-

import random

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError


class IkeEventSupplierLink(models.Model):
    _inherit = 'ike.event.supplier.link'

    uncovered_authorization_required = fields.Boolean(compute='_compute_uncovered_authorization_required', store=True, copy=False)

    # === COMPUTES === #
    @api.depends('supplier_product_ids', 'supplier_product_ids.covered', 'supplier_product_ids.authorization_id')
    def _compute_uncovered_authorization_required(self):
        for rec in self:
            rec.uncovered_authorization_required = bool(
                self.supplier_product_ids.filtered(lambda x: not x.covered and not x.authorization_id)
            )


class IkeEvent(models.Model):
    _inherit = 'ike.event'

    previous_amount = fields.Float(string="Previous Amount", compute='_compute_supplier_amount', store=True, copy=False)
    current_amount = fields.Float(string="Current Amount", compute='_compute_supplier_amount', store=True, copy=False)

    uncovered_authorization_required = fields.Boolean(compute='_compute_uncovered_authorization_required', store=True, copy=False)
    authorization_required = fields.Boolean(compute='_compute_authorization_required', store=True, copy=False)

    authorization_ids = fields.One2many('ike.event.authorization', 'event_id', copy=False)

    # === COMPUTES === #
    @api.depends(
        'service_supplier_link_ids',
        'service_supplier_link_ids.uncovered_authorization_required',
        'supplier_number')
    def _compute_uncovered_authorization_required(self):
        for rec in self:
            rec.uncovered_authorization_required = bool(rec.service_supplier_link_ids.filtered(
                lambda x:
                    x.supplier_number == rec.supplier_number
                    and x.uncovered_authorization_required)
            )

    @api.depends(
        'uncovered_authorization_required',
        'previous_amount',
        'current_amount',
        'authorized_amount')
    def _compute_authorization_required(self):
        for rec in self:
            rec.authorization_required = (
                rec.uncovered_authorization_required
                or (rec.previous_amount + rec.current_amount) > rec.authorized_amount
            )

    @api.depends(
        'supplier_search_number',
        'service_supplier_ids',
        'service_supplier_ids.selected',
        'service_supplier_ids.cancelled',
        'service_supplier_ids.amount_concept_total')
    def _compute_supplier_amount(self):
        for event_id in self:
            # Previous
            previous_amount = 0
            previous_selected = event_id.service_supplier_ids.filtered(
                lambda supplier_id:
                    supplier_id.search_number < event_id.supplier_search_number
                    and supplier_id.selected
                    and not str(supplier_id.state).startswith('cancel_')
            ).mapped('amount_concept_total')
            if previous_selected:
                previous_amount = sum(previous_selected)

            # Current
            current_amount = 0
            current_selected = event_id.service_supplier_ids.filtered(
                lambda supplier_id:
                    supplier_id.search_number == event_id.supplier_search_number
                    and supplier_id.selected
                    and not str(supplier_id.state).startswith('cancel_')
            ).mapped('amount_concept_total')
            if current_selected:
                # Current Selected
                current_amount = sum(current_selected)
            else:
                # Max Amount
                current_amounts = event_id.service_supplier_ids.filtered(
                    lambda supplier_id:
                        supplier_id.search_number == event_id.supplier_search_number
                        and not supplier_id.selected
                        and not str(supplier_id.state).startswith('cancel_')
                ).mapped('amount_concept_total')

                current_amount = max(current_amounts, default=0)

            event_id.previous_amount = previous_amount
            event_id.current_amount = current_amount

    # === SUPPLIER AUTHORIZATION ACTIONS === #
    def accept_authorization(self, event_authorization_id: int):
        self.ensure_one()
        for link_id in self.service_supplier_link_ids.filtered(
            lambda x: x.supplier_number <= self.supplier_number
        ):
            for product_id in link_id.supplier_product_ids:
                if product_id.authorization_pending:
                    product_id.authorization_ids = [
                        Command.create(
                            {
                                'event_authorization_id': event_authorization_id,
                                'quantity': product_id.quantity,
                                'unit_price': product_id.unit_price,
                                'amount': product_id.subtotal,
                            }
                        )
                    ]
                    product_id.authorization_pending = False

    def action_open_request_authorization(self):
        supplier_with_max_amount = self.get_most_expensive_supplier()
        return supplier_with_max_amount.action_view_products()

    def action_authorize_amount(self):
        for rec in self:
            supplier_with_max_amount = rec.get_most_expensive_supplier()
            supplier_with_max_amount.action_accept_authorization()

    def action_start_notifications(self):
        """ This function manually initiates automatic notifications."""
        for rec in self:
            if rec.service_supplier_ids.filtered(
                lambda x:
                    x.search_number == rec.supplier_search_number
                    and x.state in ['accepted', 'assigned']
                    and not x.display_type
            ):
                continue
            line_ids = rec.service_supplier_ids.filtered(
                lambda x:
                    x.search_number == rec.supplier_search_number
                    and x.state == 'available'
                    and not x.display_type
            )
            if line_ids:
                if line_ids[0].assignation_type == 'electronic':
                    line_ids[0].action_notify()
                elif line_ids[0].assignation_type in ['publication', 'manual']:
                    line_ids.action_notify()

    def get_most_expensive_supplier(self):
        suppliers = self.service_supplier_ids.filtered(
            lambda x: x.search_number == self.supplier_search_number and not x.display_type
        )

        if not suppliers:
            raise UserError(_('No suppliers were found'))

        supplier_with_max_amount = max(suppliers, key=lambda x: x.amount_concept_total)
        return supplier_with_max_amount

    def action_view_ike_event_service_cost(self):
        supplier_links = self.selected_supplier_ids.filtered(
            lambda x: x.state not in ['cancel_supplier', 'cancel']).mapped('supplier_link_id')

        suppliers = self.env['ike.event.supplier'].browse(supplier_links.ids)
        return suppliers.action_view_ike_event_service_cost()

    def action_view_ike_event_agreement_cost_final(self):
        supplier_links = self.selected_supplier_ids.filtered(
            lambda x: x.state not in ['cancel_supplier', 'cancel']).mapped('supplier_link_id')

        suppliers = self.env['ike.event.supplier'].browse(supplier_links.ids)
        return suppliers.action_view_ike_event_agreement_cost_final()


class IkeEventAuthorization(models.Model):
    _name = 'ike.event.authorization'
    _description = 'Event Authorization'
    _rec_name = 'create_uid'
    _order = 'id desc'

    # === KEY FIELDS === #
    event_id = fields.Many2one('ike.event', required=True)
    supplier_id = fields.Many2one('res.partner', required=True)
    supplier_number = fields.Integer(default=1, required=True)

    # === FIELDS === #
    authorized_amount = fields.Float(default=0)
    type_authorization_id = fields.Many2one('custom.additional.concept.authorizer.type')
    reason_authorizer_id = fields.Many2one('custom.reason.authorizing.additional.costs')
    authorization_by_nu = fields.Boolean()
    authorizer_id = fields.Many2one('res.partner', string="Responsible Name")
    authorizer = fields.Char()

    create_date = fields.Datetime(string='Authorization Date')
