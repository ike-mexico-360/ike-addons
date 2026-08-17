# -*- coding: utf-8 -*-
from odoo import models, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _sync_data_to_po_lines(self):
        """Propagates invoice status and creation date directly to linked Purchase Order Lines."""
        for move in self:
            if move.move_type == 'in_invoice':
                for line in move.line_ids:
                    po_line = line.purchase_line_id
                    if po_line:
                        vals = {}
                        if hasattr(move, 'x_status_invoice') and move.x_status_invoice:
                            vals['x_status_invoice'] = move.x_status_invoice

                        if move.create_date and not po_line.x_upload_invoice_date:
                            vals['x_upload_invoice_date'] = move.create_date

                        if vals:
                            po_line.write(vals)

    @api.model
    def _cron_sync_po_lines_invoice_data(self):
        """
        Cron job method for Mexico localization (ike_event_purchase_mx).
        Retroactively syncs x_upload_invoice_date and x_status_invoice
        to Purchase Order Lines from existing Vendor Bills.
        """
        vendor_bills = self.search([
            ('move_type', '=', 'in_invoice'),
            ('line_ids.purchase_line_id', '!=', False)
        ])

        for move in vendor_bills:
            for line in move.line_ids:
                po_line = line.purchase_line_id
                if po_line:
                    vals = {}

                    if move.create_date and not po_line.x_upload_invoice_date:
                        vals['x_upload_invoice_date'] = move.create_date

                    if hasattr(move, 'x_status_invoice') and move.x_status_invoice:
                        vals['x_status_invoice'] = move.x_status_invoice

                    if vals:
                        po_line.write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        moves = super(AccountMove, self).create(vals_list)
        moves._sync_data_to_po_lines()
        return moves

    def action_post(self):
        res = super(AccountMove, self).action_post()
        self._sync_data_to_po_lines()
        return res

    def button_draft(self):
        res = super(AccountMove, self).button_draft()
        self._sync_data_to_po_lines()
        return res

    def action_paid(self):
        res = super(AccountMove, self).action_paid() if hasattr(super(AccountMove, self), 'action_paid') else None
        self._sync_data_to_po_lines()
        return res

    def button_cancel(self):
        res = super(AccountMove, self).button_cancel()
        self._sync_data_to_po_lines()
        return res
