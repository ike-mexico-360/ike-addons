# -*- coding: utf-8 -*-
from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Campos Computados para la Cabecera (Consolidan las facturas vinculadas)
    x_status_invoices = fields.Char(
        string='Invoice Status (Summary)',
        compute='_compute_invoices_summary',
        store=True,
        help="Summary of vendor bills references and their respective statuses."
    )
    x_upload_invoices_date = fields.Char(
        string='Invoices Creation Date (Summary)',
        compute='_compute_invoices_summary',
        store=True,
        help='Stores the date and time when the vendor bills or XML invoices was uploaded.'
    )

    @api.depends('order_line.x_status_invoice', 'order_line.x_upload_invoice_date', 'order_line.invoice_lines.move_id.ref')
    def _compute_invoices_summary(self):
        """
        Computes and concatenates the invoice reference with its respective status and creation date.
        Example:
        - x_status_invoices: "ref221 Paid, ref63535 Accepted"
        - x_upload_invoices_date: "ref221 23/07/2026, ref63535 26/07/2026"
        """
        for order in self:
            status_list = []
            date_list = []
            seen_moves = set()

            # Iterate through purchase order lines linked to invoice lines
            for line in order.order_line:
                for inv_line in line.invoice_lines:
                    move = inv_line.move_id
                    # Filter active vendor bills that have not been processed yet
                    if move and move.move_type == 'in_invoice' and move.state != 'cancel' and move.id not in seen_moves:
                        seen_moves.add(move.id)
                        ref = move.ref or move.name or 'No Ref'

                        # 1. Build invoice status summary
                        status_val = dict(line._fields['x_status_invoice'].selection).get(line.x_status_invoice, line.x_status_invoice or '')
                        if status_val:
                            status_list.append(f"{ref} {status_val}")

                        # 2. Build upload date summary
                        if line.x_upload_invoice_date:
                            # Format date as DD/MM/YYYY for readability
                            formatted_date = line.x_upload_invoice_date.strftime('%d/%m/%Y')
                            date_list.append(f"{ref} {formatted_date}")

            order.x_status_invoices = ", ".join(status_list) if status_list else False
            order.x_upload_invoices_date = ", ".join(date_list) if date_list else False


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    x_status_invoice = fields.Selection(
        selection=[
            ('under_review', 'Under Review'),
            ('accepted', 'Accepted'),
            ('paid', 'Paid'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='Invoice Status',
        default='under_review',
        copy=False,
    )
    x_upload_invoice_date = fields.Datetime(
        string='Invoice Upload Date',
        readonly=True,
        copy=False,
        help='Stores the date and time when the vendor bill or XML invoice was uploaded.'
    )
