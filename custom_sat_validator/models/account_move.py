
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
    x_xml_file = fields.Binary(
        string='File XML',
        help='Select the XML file of the electronic invoice',
        readonly=True
    )
    x_xml_filename = fields.Char(string='Name file', readonly=True)
    x_importing_xml = fields.Boolean(
        string='Importing XML',
        default=False,
        help='Indicates whether an XML file is being imported',
        readonly=True
    )
    x_vendor_bill_pdf_file = fields.Binary(
        string="Vendor Bill PDF",
        attachment=True,
        copy=False
    )
    x_vendor_bill_pdf_name = fields.Char(string="Vendor Bill PDF Name")

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
