# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # Migrate code custom_sat_validatos
    # x_status_invoices = fields.Char(
    #     string='Invoice Status (Summary)',
    #     compute='_compute_invoices_summary',
    #     store=True,
    #     help="Summary of vendor bills references and their respective statuses."
    # )
    # x_upload_invoices_date = fields.Char(
    #     string='Invoices Upload Date (Summary)',
    #     compute='_compute_invoices_summary',
    #     store=True,
    #     help='Stores the date and time when the vendor bills or XML invoices was uploaded.'
    # )

    # @api.depends('order_line.x_status_invoice', 'order_line.x_upload_invoice_date', 'order_line.invoice_lines.move_id.ref')
    # def _compute_invoices_summary(self):
    #     """
    #     Computes and concatenates the invoice reference with its respective status and creation date.
    #     """
    #     # Ensure evaluation runs in Spanish context (or user context)
    #     lang = self.env.user.lang or 'es_MX'
    #     env = self.env['base'].with_context(lang=lang).env

    #     for order in self:
    #         status_list = []
    #         date_list = []
    #         seen_moves = set()

    #         # Iterate through purchase order lines linked to invoice lines
    #         for line in order.order_line:
    #             # Bind the line to the environment with language context
    #             line_ctx = line.with_env(env)
    #             for inv_line in line_ctx.invoice_lines:
    #                 move = inv_line.move_id
    #                 if move and move.move_type == 'in_invoice' and move.state != 'cancel' and move.id not in seen_moves:
    #                     seen_moves.add(move.id)
    #                     ref = move.ref or move.name or 'No Ref'

    #                     # 1. Build invoice status summary using language context
    #                     selection_labels = dict(line_ctx._fields['x_status_invoice']._description_selection(env))
    #                     status_val = selection_labels.get(line_ctx.x_status_invoice, line_ctx.x_status_invoice or '')
    #                     if status_val:
    #                         status_list.append(f"{ref} {status_val}")

    #                     # 2. Build upload date summary
    #                     if line_ctx.x_upload_invoice_date:
    #                         formatted_date = line_ctx.x_upload_invoice_date.strftime('%d/%m/%Y')
    #                         date_list.append(f"{ref} {formatted_date}")

    #         order.x_status_invoices = ", ".join(status_list) if status_list else False
    #         order.x_upload_invoices_date = ", ".join(date_list) if date_list else False

# Migrate code ike_event_purchase
# class PurchaseOrderLine(models.Model):
#     _inherit = 'purchase.order.line'

#     x_status_invoice = fields.Selection(
#         selection=[
#             ('under_review', 'Under Review'),
#             ('accepted', 'Accepted'),
#             ('paid', 'Paid'),
#             ('rejected', 'Rejected'),
#             ('cancelled', 'Cancelled'),
#         ],
#         string='Invoice Status',
#         copy=False,
#     )
#     x_upload_invoice_date = fields.Datetime(
#         string='Invoice Upload Date',
#         readonly=True,
#         copy=False,
#         help='Stores the date and time when the vendor bill or XML invoice was uploaded.'
#     )
