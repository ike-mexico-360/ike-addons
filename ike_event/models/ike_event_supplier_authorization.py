# -*- coding: utf-8 -*-

import random

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError


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
        'service_supplier_ids.amount_concept_total',
        'service_supplier_ids.evaluation_id',
    )
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
                        and (
                            not supplier_id.assignation_type.startswith('manual')
                            or supplier_id.evaluation_id
                            and supplier_id.evaluation_reevaluation
                        )
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
                if product_id.authorization_pending or not product_id.covered and not product_id.authorization_id:
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
        if self.uncovered_authorization_required:
            self.service_supplier_link_ids._compute_uncovered_authorization_required()

    def action_open_request_authorization(self):
        self.ensure_one()
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
                elif line_ids[0].assignation_type in ['publication']:
                    line_ids.action_notify()

    def get_most_expensive_supplier(self):
        suppliers = self.service_supplier_ids.filtered(
            lambda x:
                x.search_number == self.supplier_search_number and not x.display_type
                and (not x.assignation_type.startswith('manual') or not x.evaluation_locked)
        )

        if not suppliers:
            raise UserError(_('No suppliers were found'))

        supplier_with_max_amount = max(suppliers, key=lambda x: x.amount_concept_total)
        return supplier_with_max_amount

    def action_view_ike_event_service_cost(self):
        return self.selected_supplier_ids.action_view_ike_event_service_cost()

    def action_view_ike_event_agreement_cost_final(self):
        return self.selected_supplier_ids.action_view_ike_event_agreement_cost_final()


class IkeEventSupplier(models.Model):
    _inherit = 'ike.event.supplier'

    # === FIELDS === #
    type_authorization_id = fields.Many2one(related='supplier_link_id.type_authorization_id', readonly=False)
    reason_authorizer_id = fields.Many2one(related='supplier_link_id.reason_authorizer_id', readonly=False)
    authorization_by_nu = fields.Boolean(related='supplier_link_id.authorization_by_nu', string='Is Authorized By Nu', readonly=False)
    authorizer_id = fields.Many2one(related='supplier_link_id.authorizer_id', readonly=False)
    authorizer_domain = fields.Binary(compute="_compute_authorizer_domain")
    nu_user_id = fields.Many2one(related='event_id.user_id')

    # === ONCHANGE === #
    @api.onchange('type_authorization_id')
    def onchange_type_authorization_id(self):
        if self.type_authorization_id.id != self._origin.type_authorization_id.id:
            self.authorizer_id = False
        self.authorization_by_nu = False if not self.type_authorization_id.is_nu else True

    # === COMPUTE === #
    @api.depends('type_authorization_id', 'authorizer_id')
    def _compute_authorizer_domain(self):
        for rec in self:
            domain = []
            if rec.type_authorization_id.is_client:
                client_ids = self.env['res.partner'].search([
                    ('is_company', '=', True),
                    ('x_is_client', '=', True)
                ])
                domain = [('disabled', '=', False), ('id', 'in', client_ids.ids)]
            if rec.type_authorization_id.is_user_internal:
                user_internal_ids = self.env['res.users'].search([
                    ('share', '=', False),
                ]).mapped("partner_id")
                domain = [('disabled', '=', False), ('id', 'in', user_internal_ids.ids)]
            rec.authorizer_domain = domain

    # === ACTIONS === #
    def action_request_authorization(self):
        self.supplier_link_id.sudo().action_request_authorization()

    def action_accept_authorization(self):
        self.supplier_link_id.sudo().action_accept_authorization()

    def action_reject_authorization(self):
        self.supplier_link_id.sudo().action_reject_authorization()


class IkeEventSupplierLink(models.Model):
    _inherit = 'ike.event.supplier.link'

    # === FIELDS === #
    uncovered_authorization_required = fields.Boolean(compute='_compute_uncovered_authorization_required', store=True, copy=False)

    # === COMPUTES === #
    @api.depends('supplier_product_ids', 'supplier_product_ids.covered', 'supplier_product_ids.authorization_id')
    def _compute_uncovered_authorization_required(self):
        for rec in self:
            rec.uncovered_authorization_required = bool(
                self.supplier_product_ids.filtered(lambda x: not x.covered and not x.authorization_id)
            )

    # === ACTION === #
    def action_save_and_request_authorization(self):
        for rec in self:
            supplier = self.env['ike.event.supplier'].search([
                ('supplier_link_id', '=', rec.id)
            ], limit=1)

            if supplier:
                supplier.action_request_authorization()

        return True

    def action_request_authorization(self):
        self.ensure_one()

        if self.authorization_by_nu and not self.user_payment_line_ids:
            raise UserError(
                _("The authorization type requires a payment line.")
            )
        # ToDo: Send notification?

    def action_accept_authorization(self):
        self.ensure_one()
        event_id = self.event_id.sudo()

        if not self.type_authorization_id and not self.reason_authorizer_id:
            raise ValidationError(
                _("Authorization is not possible because there are incomplete authorization fields.")
            )

        if self.authorization_by_nu and not self.user_payment_line_ids:
            raise UserError(
                _("The authorization type requires a payment line.")
            )

        authorized_amount = max(event_id.previous_amount + event_id.current_amount, event_id.covered_amount)
        authorizer = (
            self.nu_user_id.display_name
            if self.authorization_by_nu
            else self.authorizer_id.display_name
        )
        event_id.authorized_amount = authorized_amount
        event_authorization_id = self.sudo().env['ike.event.authorization'].create({
            'event_id': self.event_id.id,
            'supplier_id': self.supplier_id.id,
            'supplier_number': self.supplier_number,
            'authorized_amount': authorized_amount,
            'type_authorization_id': self.type_authorization_id.id,
            'reason_authorizer_id': self.reason_authorizer_id.id,
            'authorization_by_nu': self.authorization_by_nu,
            'authorizer_id': self.authorizer_id and self.authorizer_id.id,
            'authorizer': authorizer,
        })
        event_id.accept_authorization(event_authorization_id.id)

        if event_id.supplier_search_type in ['manual_manual', 'manual']:
            event_id.broadcastEventReload(1)

        # Start automatic notifications
        event_id.action_start_notifications()

    def action_reject_authorization(self):
        self.ensure_one()
        # ToDo: Reject?
        print("action_reject_authorization")


class IkeEventSupplierProduct(models.Model):
    _inherit = 'ike.event.supplier.product'

    # === FIELDS === #
    authorization_pending = fields.Boolean(default=True)
    authorization_ids = fields.One2many(
        'ike.event.supplier.product.authorization', 'event_supplier_product_id',
        string='Authorizations')
    authorization_id = fields.Many2one(
        'ike.event.supplier.product.authorization',
        compute='_compute_authorization_id', store=True,
        string='Authorization')
    type_authorization_id = fields.Many2one(related='authorization_id.event_authorization_id.type_authorization_id', store=True)
    authorizer_name = fields.Char(related='authorization_id.event_authorization_id.authorizer', string='Authorized', store=True)

    # === COMPUTES === #
    @api.depends('authorization_ids')
    def _compute_authorization_id(self):
        for rec in self:
            if rec.authorization_ids:
                rec.authorization_id = rec.authorization_ids[0].id
            else:
                rec.authorization_id = None


class IkeEventAuthorization(models.Model):
    _name = 'ike.event.authorization'
    _description = 'Event Authorization'
    _rec_name = 'create_uid'
    _order = 'id desc'

    # === KEY FIELDS === #
    event_id = fields.Many2one('ike.event', ondelete='cascade', required=True)
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
