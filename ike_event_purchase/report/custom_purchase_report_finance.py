# -*- coding: utf-8 -*-
from odoo import fields, models, api
from odoo.tools.query import Query
from odoo.tools.sql import SQL

ALLOWED_PO_STATES = ('purchase', 'done')


class CustomPurchaseReportFinance(models.Model):
    _name = "custom.purchase.report.finance"
    _description = "Purchase and Invoice Header Report"
    _auto = False
    _order = 'date_order desc'

    # Purchase Order Header Fields
    order_id = fields.Many2one('purchase.order', 'Reference', readonly=True)
    date_order = fields.Datetime('Order Date', readonly=True)
    date_approve = fields.Datetime('Confirmation Date', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Vendor', readonly=True)
    commercial_partner_id = fields.Many2one('res.partner', 'Commercial Entity', readonly=True)
    country_id = fields.Many2one('res.country', 'Partner Country', readonly=True)
    user_id = fields.Many2one('res.users', 'Buyer', readonly=True)
    company_id = fields.Many2one('res.company', 'Company', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Currency', readonly=True)
    origin = fields.Char('Document Origin', readonly=True)
    x_origin_events = fields.Char('Origin Events', readonly=True)
    x_po_ref_sap = fields.Char('PO SAP', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('purchase', 'Purchase Order'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], 'Status', readonly=True)
    invoice_status = fields.Selection([
        ('no', 'Nothing to Bill'),
        ('to invoice', 'Waiting Bills'),
        ('invoiced', 'Fully Billed'),
    ], 'Billing Status', readonly=True)

    amount_untaxed = fields.Monetary('Untaxed Total', readonly=True)
    amount_total = fields.Monetary('Total', readonly=True)

    # Invoice Header Fields
    invoice_id = fields.Many2one('account.move', 'Invoice', readonly=True)
    invoice_name = fields.Char('Invoice Number', readonly=True)
    x_invoice_ref_sap = fields.Char('Invoice SAP', readonly=True)
    invoice_date = fields.Date('Invoice Date', readonly=True)
    invoice_state = fields.Selection([
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('cancel', 'Cancelled')
    ], 'Invoice State', readonly=True)
    x_status_invoice = fields.Selection(
        selection=[
            ('under_review', 'Under Review'),
            ('accepted', 'Accepted'),
            ('paid', 'Paid'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Invoice Statuses',
        readonly=True
    )
    invoice_payment_state = fields.Selection([
        ('not_paid', 'Not Paid'),
        ('in_payment', 'In Payment'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('reversed', 'Reversed'),
        ('invoicing_legacy', 'Invoicing App Legacy')
    ], 'Payment Status', readonly=True)

    @property
    def _table_query(self) -> SQL:
        return SQL("%s %s %s", self._select(), self._from(), self._where())

    def _select(self) -> SQL:
        return SQL(
            """
                SELECT
                    -- Unique ID for view aggregation (combining PO and Invoice)
                    ROW_NUMBER() OVER () as id,
                    po.id as order_id,
                    po.date_order as date_order,
                    po.date_approve as date_approve,
                    po.partner_id as partner_id,
                    partner.commercial_partner_id as commercial_partner_id,
                    partner.country_id as country_id,
                    po.user_id as user_id,
                    po.company_id as company_id,
                    po.currency_id as currency_id,
                    po.origin as origin,
                    po.x_origin_events as x_origin_events,
                    po.x_ref_sap as x_po_ref_sap,
                    po.state as state,
                    po.invoice_status as invoice_status,
                    po.amount_untaxed as amount_untaxed,
                    po.amount_total as amount_total,

                    -- Related Invoice Data
                    am.id as invoice_id,
                    am.name as invoice_name,
                    am.x_ref_sap as x_invoice_ref_sap,
                    am.invoice_date as invoice_date,
                    am.state as invoice_state,
                    am.x_status_invoice as x_status_invoice,
                    am.payment_state as invoice_payment_state
            """,
        )

    def _from(self) -> SQL:
        return SQL(
            """
            FROM
                purchase_order po
                JOIN res_partner partner ON po.partner_id = partner.id
                -- Standard relation between Purchase Orders and Invoices in Odoo
                LEFT JOIN account_move_purchase_order_rel rel ON rel.purchase_order_id = po.id
                LEFT JOIN account_move am ON (am.id = rel.account_move_id AND am.move_type IN ('in_invoice', 'in_refund'))
            """,
        )

    def _where(self) -> SQL:
        return SQL(
            """
            WHERE
                po.state IN %s
            """,
            ALLOWED_PO_STATES,
        )
