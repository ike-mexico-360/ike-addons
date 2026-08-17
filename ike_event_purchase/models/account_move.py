from odoo import fields, models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

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
        tracking=True,
    )

    x_gross_sale = fields.Monetary(
        string='Gross Sale',
        compute='_compute_x_gross_sale',
        store=True,
        currency_field='currency_id',
        help='Sum of untaxed amount plus positive taxes (excludes withholdings).'
    )
    x_ref_sap = fields.Char(string='SAP Reference')

    @api.depends('amount_untaxed', 'line_ids.balance', 'line_ids.amount_currency', 'line_ids.display_type')
    def _compute_x_gross_sale(self):
        for move in self:
            if move.is_invoice(include_receipts=True):
                # Multiplier based on document type (Invoice or Credit Note)
                sign = move.direction_sign
                positive_taxes = 0.0

                # Iterate through tax lines only
                for line in move.line_ids.filtered(lambda ln: ln.display_type == 'tax'):
                    # Convert the line currency amount to match the document direction
                    tax_amount = sign * line.amount_currency

                    # Add only positive tax amounts (exclude withholdings)
                    if tax_amount > 0:
                        positive_taxes += tax_amount

                # Gross Sale = Untaxed Amount + Positive Taxes
                move.x_gross_sale = move.amount_untaxed + positive_taxes
            else:
                move.x_gross_sale = 0.0

    def action_post(self):
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.is_invoice(include_receipts=True):
                move.x_status_invoice = 'accepted'
        return res

    def button_draft(self):
        res = super(AccountMove, self).button_draft()
        for move in self:
            if move.is_invoice(include_receipts=True):
                move.x_status_invoice = 'under_review'
        return res

    def action_paid(self):
        for move in self:
            if move.is_invoice(include_receipts=True):
                move.x_status_invoice = 'paid'

    def action_rejected(self):
        for move in self:
            if move.is_invoice(include_receipts=True):
                move.x_status_invoice = 'rejected'

    def button_cancel(self):
        res = super(AccountMove, self).button_cancel()
        for move in self:
            if move.is_invoice(include_receipts=True):
                move.x_status_invoice = 'cancelled'
        return res
