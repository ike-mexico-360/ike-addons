
# -*- coding: utf-8 -*-
from odoo import models


class CustomSatValidatorLine(models.Model):
    _inherit = 'custom.sat.validator.line'

    def _create_invoice_from_xml(self):
        invoice = super(CustomSatValidatorLine, self)._create_invoice_from_xml()

        if invoice:
            for line in invoice.invoice_line_ids:
                if line.purchase_line_id:
                    po_line_vals = {}

                    if invoice.create_date:
                        po_line_vals['x_upload_invoice_date'] = invoice.create_date

                    if hasattr(invoice, 'x_status_invoice') and invoice.x_status_invoice:
                        po_line_vals['x_status_invoice'] = invoice.x_status_invoice
                    else:
                        po_line_vals['x_status_invoice'] = 'under_review'

                    if po_line_vals:
                        line.purchase_line_id.write(po_line_vals)

        return invoice
