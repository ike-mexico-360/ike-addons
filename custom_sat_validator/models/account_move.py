
from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    sat_validator_id = fields.Many2one('custom.sat.validator', string="Origin Validator SAT", readonly=True)

    x_xml_uuid = fields.Char(
            string="XML UUID",
            copy=False,
            index=True,
            help="Unique identifier (Folio Fiscal) extracted from the provider's XML."
        )

    def _generate_cfdi_pdf_bytes(self):
        """
        Renders the vendor bill PDF using Odoo's QWeb report engine.
        Returns raw PDF bytes.
        """
        self.ensure_one()

        report = self.env['ir.actions.report']._get_report_from_name('account.report_invoice')
        pdf_content, _content_type = report._render_qweb_pdf(
            report,
            res_ids=[self.id],
            data=None
        )
        return pdf_content


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_xml_line_description = fields.Char(
        string="XML Line Description",
        help="Original product/service description extracted from the vendor's XML line."
    )
