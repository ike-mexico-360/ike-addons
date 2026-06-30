# -*- coding: utf-8 -*-
import base64
import requests
from lxml import etree
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CustomSatValidator(models.Model):
    _name = 'custom.sat.validator'
    _description = 'Autonomous SAT CFDI Validator'
    _inherit = ['mail.thread']

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default=lambda self: 'New')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('xml_error', 'XML Mismatch'),
        ('validated', 'Successfully Validated'),
        ('error', 'SAT Error / Communication')
    ], string="Status", default='draft', tracking=True, readonly=True)

    purchase_id = fields.Many2one('purchase.order', string="Purchase Order", tracking=True)
    invoice_id = fields.Many2one('account.move', string="Generated Vendor Bill", readonly=True, copy=False)

    xml_file = fields.Binary(string="CFDI XML File", required=True, copy=False)
    xml_filename = fields.Char(string="XML File Name")

    emisor_rfc = fields.Char(string="Issuer RFC", readonly=True, index=True)
    receptor_rfc = fields.Char(string="Receiver RFC", readonly=True)
    subtotal_amount = fields.Float(string="XML Subtotal", digits=(16, 2), readonly=True)
    total_amount = fields.Float(string="XML Total", digits=(16, 2), readonly=True)
    sat_uuid = fields.Char(string="UUID (Fiscal Folio)", readonly=True, index=True, copy=False)
    xml_invoice_date = fields.Date(
        string="XML Emission Date",
        readonly=True,
        help="The official emission date extracted directly from the XML root node."
    )

    sat_status = fields.Selection([
        ('Vigente', 'Active'),
        ('Cancelado', 'Cancelled'),
        ('No Encontrado', 'Not Found'),
        ('Error', 'Communication Error')
    ], string="SAT Status", readonly=True, default='No Encontrado', copy=False, tracking=True)

    validation_log = fields.Text(string="Validation Log", readonly=True, copy=False)
    cfdi_is_valid = fields.Boolean(string="Is XML Valid?", default=False, readonly=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.sudo().env['ir.sequence'].next_by_code('custom.sat.validator') or 'VAL/'
        return super(CustomSatValidator, self).create(vals_list)

    def _check_required_purchase_order(self):
        """ Verifies if a purchase order has been selected """
        self.ensure_one()
        if not self.purchase_id:
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': _("Validation Error: Selecting a Purchase Order is strictly mandatory to audit the XML.")
            })
            return False
        return True

    def _validate_sap_reference_received(self):
        """
        Check if the SAP reference (Char field) has been received for the purchase order.
        """
        self.ensure_one()
        sap_ref = self.purchase_id.x_ref_sap

        is_empty = not sap_ref or not sap_ref.strip()
        is_string_false = sap_ref and sap_ref.strip().lower() == 'false'

        if is_empty or is_string_false:
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': _("Validation Error: The linked Purchase Order does not have a valid SAP reference configured.")
            })
            return False

        return True

    def _validate_duplicate_uuid(self, xml_uuid):
        """
        Check if a vendor bill with the same XML UUID already exists in the system.
        """
        if not xml_uuid:
            return True

        xml_uuid_upper = xml_uuid.upper()
        duplicate_bill = self.env['account.move'].search([
            ('x_xml_uuid', '=', xml_uuid_upper),
        ], limit=1)

        if duplicate_bill:
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': _("The XML UUID already exists in the system on invoice: %s.") % duplicate_bill.display_name
            })
            return False

        return True

    def _validate_receptor_rfc(self, xml_receptor_rfc):
        """ Validates XML Receptor RFC against Odoo Current Company RFC """
        self.ensure_one()
        company_rfc = self.env.company.vat

        if not company_rfc:
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': _("Validation Error: Your active company '%s' does not have an RFC (VAT) configured in Odoo.") % self.env.company.name
            })
            return False

        if xml_receptor_rfc.strip().upper() != company_rfc.strip().upper():
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': _("XML Error: The XML receiver RFC (%s) does not match your company RFC (%s). The supplier invoiced a different entity.") % (xml_receptor_rfc, company_rfc)
            })
            return False
        return True

    def _validate_emisor_rfc(self, xml_emisor_rfc):
        """ Validates XML Emisor RFC against Purchase Order Supplier RFC """
        self.ensure_one()
        partner_rfc = self.purchase_id.partner_id.vat

        if not partner_rfc:
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': _("Odoo Error: The supplier '%s' on the PO does not have an RFC configured in their contact profile.") % self.purchase_id.partner_id.name
            })
            return False

        if xml_emisor_rfc.strip().upper() != partner_rfc.strip().upper():
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': _("XML Error: The Issuer RFC (%s) does not belong to the supplier assigned to the Purchase Order (%s - %s).") % (xml_emisor_rfc, partner_rfc, self.purchase_id.partner_id.name)
            })
            return False
        return True

    def _validate_total_amount(self, xml_subtotal):
        """ Validates XML Total Amount against Purchase Order Total Amount """
        self.ensure_one()
        po_subtotal = self.purchase_id.amount_untaxed

        if round(xml_subtotal, 2) < round(po_subtotal, 2):
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': _("XML Error: The XML subtotal ($%s) does not match the expected subtotal in the Purchase Order (%s).") % (round(xml_subtotal, 2), round(po_subtotal, 2))
            })
            return False
        return True

    def _validate_date_alignment(self, xml_date):
        """
        Validates that the XML date is not ahead of the Purchase Order date
        plus the max allowed old days configuration.
        """
        self.ensure_one()
        if not self.purchase_id:
            return False

        # 1. Fetch parameters from the record's current company
        max_days = self.env.company.x_xml_max_days_old or 0

        # 2. Ensure both dates are evaluated in the same format (date object)
        po_date = self.purchase_id.date_order.date() if self.purchase_id.date_order else False

        if not po_date or not xml_date:
            return True

        # Convert string from XML parser to safe native date object if necessary
        if isinstance(xml_date, str):
            xml_date = fields.Date.from_string(xml_date)
        elif isinstance(xml_date, fields.Datetime):
            xml_date = xml_date.date()

        # 3. Apply business rule logic: (PO Date + Configured Days) < XML Date -> Trigger Error
        limit_date = po_date + timedelta(days=max_days)

        if limit_date < xml_date:
            message = _(
                "Date Error: The XML date (%s) exceeds the allowed threshold of "
                "%s day(s) after the Purchase Order creation date (%s). Maximum allowed date: %s."
            ) % (xml_date, max_days, po_date, limit_date)

            if hasattr(self, 'validation_log') and self.validation_log:
                self.validation_log = (self.validation_log or "") + f"\n{message}"
            else:
                self.validation_log = message

            return False

        return True

    def _validate_purchase_order_data(self, xml_emisor_rfc, xml_receptor_rfc, xml_subtotal, xml_uuid, xml_date=False):
        """
        Orchestrator method for internal business rules.
        Invokes atomic validations sequentially.
        """
        self.ensure_one()

        if not self._check_required_purchase_order():
            return False

        if not self._validate_sap_reference_received():
            return False

        if not self._validate_duplicate_uuid(xml_uuid):
            return False

        if not self._validate_receptor_rfc(xml_receptor_rfc):
            return False

        if not self._validate_emisor_rfc(xml_emisor_rfc):
            return False

        if not self._validate_total_amount(xml_subtotal):
            return False

        if xml_date and not self._validate_date_alignment(xml_date):
            return False
        return True

    def _parse_and_extract_xml_data(self):
        """
        Reads, decodes, and parses the binary XML file.
        Extracts structural attributes and writes them to the record.
        """
        self.ensure_one()
        if not self.xml_file:
            raise ValidationError(_("Please, upload an XML file."))

        if self.xml_filename and not self.xml_filename.lower().endswith('.xml'):
            raise ValidationError(_("The file must have an .xml extension."))

        xml_content = base64.b64decode(self.xml_file)
        xml_doc = etree.fromstring(xml_content)

        namespaces = {
            'cfdi': 'http://www.sat.gob.mx/cfd/4',
            'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital',
        }

        emisor_node = xml_doc.xpath("//cfdi:Emisor", namespaces=namespaces)
        receptor_node = xml_doc.xpath("//cfdi:Receptor", namespaces=namespaces)
        timbre_node = xml_doc.xpath("//tfd:TimbreFiscalDigital", namespaces=namespaces)

        if not timbre_node:
            self.write({
                'state': 'error',
                'cfdi_is_valid': False,
                'validation_log': _("Error: The XML does not contain the mandatory 'TimbreFiscalDigital' node.")
            })
            return False

        raw_fecha = xml_doc.get("Fecha") or xml_doc.get("fecha")
        extracted_date = False
        if raw_fecha:
            # ISO format standard: 'YYYY-MM-DDTHH:MM:SS', split by 'T' to get only 'YYYY-MM-DD'
            xml_date_str = raw_fecha.split('T')[0]
            extracted_date = fields.Date.from_string(xml_date_str)

        extracted_emisor_rfc = emisor_node[0].get("Rfc") if emisor_node else False
        extracted_receptor_rfc = receptor_node[0].get("Rfc") if receptor_node else False
        subtotal_str = xml_doc.get("SubTotal")
        total_str = xml_doc.get("Total")
        extracted_uuid = timbre_node[0].get("UUID")

        xml_subtotal_float = float(subtotal_str or 0.0)
        xml_total_float = float(total_str or 0.0)

        self.write({
            'emisor_rfc': extracted_emisor_rfc,
            'receptor_rfc': extracted_receptor_rfc,
            'total_amount': xml_total_float,
            'subtotal_amount': xml_subtotal_float,
            'sat_uuid': extracted_uuid,
            'xml_invoice_date': extracted_date,
        })

        return {
            'xml_emisor_rfc': extracted_emisor_rfc,
            'xml_receptor_rfc': extracted_receptor_rfc,
            'xml_subtotal': xml_subtotal_float,
            'xml_total': xml_total_float,
            'xml_uuid': extracted_uuid,
            'xml_date': extracted_date
        }

    def _request_sat_web_service(self, xml_emisor_rfc, xml_receptor_rfc, xml_total, xml_uuid):
        """
        Prepares the SOAP envelope, sends the POST request to SAT Web Service,
        and parses the response status. Handles explicit connection and HTTP errors.
        """
        self.ensure_one()
        total_formatted = f"{xml_total:.6f}"

        soap_url = "https://consultaqr.facturaelectronica.sat.gob.mx/Consultacfdiservice.svc"
        headers = {
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': 'http://tempuri.org/IConsultaCFDIService/Consulta'
        }

        soap_xml = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:Consulta>
         <tem:expresionImpresa><![CDATA[?re={xml_emisor_rfc}&rr={xml_receptor_rfc}&tt={total_formatted}&id={xml_uuid}]]></tem:expresionImpresa>
      </tem:Consulta>
   </soapenv:Body>
</soapenv:Envelope>"""

        try:
            response = requests.post(soap_url, data=soap_xml, headers=headers, timeout=10)
        except requests.exceptions.RequestException as connection_error:
            # Explicit network/timeout error targeting the external SAT infrastructure
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'state': 'error',
                'validation_log': _("SAT Server Connectivity Error: %s") % str(connection_error)
            })
            return False

        if response.status_code == 200:
            try:
                root = ET.fromstring(response.content)
                ns = {'a': 'http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio'}

                estado_sat = root.find('.//a:Estado', ns)
                codigo_estatus = root.find('.//a:CodigoEstatus', ns)

                status_res = estado_sat.text if estado_sat is not None else 'No Encontrado'
                codigo_res = codigo_estatus.text if codigo_estatus is not None else 'S/N'

                is_valid = (status_res == 'Vigente')

                self.write({
                    'sat_status': status_res if status_res else 'No Encontrado',
                    'cfdi_is_valid': is_valid,
                    'state': 'validated' if is_valid else 'error',
                    'validation_log': _("Successful Parse.\nSAT Response Code: %s\nCurrent Status: %s.\n") % (codigo_res, status_res)
                })
                return True
            except Exception as parsing_soap_error:
                # The SAT responded HTTP 200, but sent a corrupted or unexpected SOAP response structure
                self.write({
                    'sat_status': 'Error',
                    'cfdi_is_valid': False,
                    'state': 'error',
                    'validation_log': _("SAT Response Payload Parse Error: %s") % str(parsing_soap_error)
                })
                return False
        else:
            # Explicit HTTP error codes returned from the SAT server (e.g., 500, 503, 404)
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'state': 'error',
                'validation_log': _("SAT Server Response Error (HTTP %s). Infrastructure might be down.") % response.status_code
            })
            return False

    def _prepare_invoice_header(self):
        """
        Prepares the dictionary dictionary values for the account.move header.
        """
        self.ensure_one()
        # Fallback to current purchase_id partner or search via RFC
        partner_id = self.purchase_id.partner_id.id if self.purchase_id else self.env['res.partner'].search([('vat', '=', self.emisor_rfc)], limit=1).id

        return {
            'move_type': 'in_invoice',
            'partner_id': partner_id,
            'invoice_origin': self.purchase_id.name if self.purchase_id else False,
            'purchase_id': self.purchase_id.id if self.purchase_id else False,
            'currency_id': self.purchase_id.currency_id.id if self.purchase_id else self.env.company.currency_id.id,
            'invoice_date': fields.Date.context_today(self),
            'sat_validator_id': self.id,
            'x_xml_uuid': self.sat_uuid.upper() if self.sat_uuid else False,
        }

    def _get_xml_global_taxes(self, xml_doc, namespaces):
        """
        Extracts distinctive rates from individual concepts to form a verified
        global tax template, avoiding the missing 'TasaOCuota' attribute on SAT's
        summary closing nodes.
        """
        self.ensure_one()
        tax_ids = []

        # 1. Inspect Concept Nodes to find all unique Transferred Taxes (e.g., IVA 16%)
        concept_transfers = xml_doc.xpath("//cfdi:Concepto/cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", namespaces=namespaces)
        for transfer in concept_transfers:
            rate_str = transfer.get("TasaOCuota")
            if rate_str:
                amount_percentage = float(rate_str) * 100
                tax = self.env['account.tax'].search([
                    ('amount', '>=', amount_percentage - 0.005),
                    ('amount', '<=', amount_percentage + 0.005),
                    ('type_tax_use', '=', 'purchase'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if tax and tax.id not in tax_ids:
                    tax_ids.append(tax.id)

        # 2. Inspect Concept Nodes to find all unique Withheld Taxes (ISR 1.25% / IVA 10.67%)
        concept_withholdings = xml_doc.xpath("//cfdi:Concepto/cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion", namespaces=namespaces)
        for withholding in concept_withholdings:
            rate_str = withholding.get("TasaOCuota")
            if rate_str:
                amount_percentage = float(rate_str) * -100  # Convert to negative for Odoo withholdings
                tax = self.env['account.tax'].search([
                    ('amount', '>=', amount_percentage - 0.005),
                    ('amount', '<=', amount_percentage + 0.005),
                    ('type_tax_use', '=', 'purchase'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if tax and tax.id not in tax_ids:
                    tax_ids.append(tax.id)

        return tax_ids

    def _get_xml_line_taxes(self, line_node, namespaces):
        """
        Extracts transferred and withheld taxes from an individual cfdi:Concepto node.
        Used as fallback strategy if distinct distribution per item is requested.
        """
        self.ensure_one()
        tax_ids = []

        # 1. Line Transferred Taxes
        line_transfers = line_node.xpath(".//cfdi:Impuestos/cfdi:Traslados/cfdi:Traslado", namespaces=namespaces)
        for transfer in line_transfers:
            rate_str = transfer.get("TasaOCuota")
            if rate_str:
                amount_percentage = float(rate_str) * 100
                tax = self.env['account.tax'].search([
                    ('amount', '>=', amount_percentage - 0.005),
                    ('amount', '<=', amount_percentage + 0.005),
                    ('type_tax_use', '=', 'purchase'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if tax and tax.id not in tax_ids:
                    tax_ids.append(tax.id)

        # 2. Line Withheld Taxes
        line_withholdings = line_node.xpath(".//cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion", namespaces=namespaces)
        for withholding in line_withholdings:
            rate_str = withholding.get("TasaOCuota")
            if rate_str:
                amount_percentage = float(rate_str) * -100
                tax = self.env['account.tax'].search([
                    ('amount', '>=', amount_percentage - 0.005),
                    ('amount', '<=', amount_percentage + 0.005),
                    ('type_tax_use', '=', 'purchase'),
                    ('company_id', '=', self.env.company.id)
                ], limit=1)
                if tax and tax.id not in tax_ids:
                    tax_ids.append(tax.id)

        return tax_ids

    def _find_matching_purchase_line(self, po_lines, xml_subtotal, matched_po_ids, tolerance=0.05):
        """
        Atomic method to find the correct Purchase Order Line using STRICT Subtotal match.
        """
        if not po_lines:
            return False

        for po_line in po_lines:
            if po_line.id in matched_po_ids:
                continue

            po_pending_subtotal = po_line.price_unit * po_line.qty_to_invoice
            # Strict validation only by pending subtotal amount
            if abs(po_pending_subtotal - xml_subtotal) <= tolerance:
                return po_line

        return False

    def _prepare_invoice_lines(self, xml_doc, namespaces, global_tax_ids=False):
        """
        Extracts data from XML nodes and maps them to PO lines.
        Forces quantities and prices directly from XML attributes.
        """
        self.ensure_one()
        invoice_lines = []
        concept_nodes = xml_doc.xpath("//cfdi:Concepto", namespaces=namespaces)
        # Filter actively for purchase order lines that have not been fully invoiced yet
        po_lines = self.purchase_id.order_line.filtered(lambda l: l.qty_to_invoice > 0) if self.purchase_id else False
        # Internal list to track and prevent duplicate matches within the same XML processing loop
        matched_po_line_ids = []

        # --- STEP 1: STRICT PRE-VALIDATION BY AMOUNT ---
        if not po_lines and concept_nodes:
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'state': 'error',
                'validation_log': _("The Purchase Order has no pending lines to invoice, but XML contains items.")
            })
            return []

        for line in concept_nodes:
            xml_subtotal = float(line.get("Importe") or 0.0)
            description = line.get("Descripcion") or "Unknown item"

            # Invoke the external function to find the matching PO line by subtotal, code, or name
            matched_line = self._find_matching_purchase_line(
                po_lines=po_lines,
                xml_subtotal=xml_subtotal,
                matched_po_ids=matched_po_line_ids
            )

            if not matched_line:
                # Build custom error message with XML item description and amount
                error_msg = _(
                    "Verification Failed: Mismatched Document Structure The XML line '%(desc)s' with amount $%(amount).2f "
                    "could not be matched with any available line in the Purchase Order."
                ) % {
                    'desc': description,
                    'amount': xml_subtotal
                }

                # Write status and log into the current record instead of throwing a raise
                self.write({
                    'sat_status': 'Error',
                    'cfdi_is_valid': False,
                    'state': 'error',
                    'validation_log': error_msg
                })
                return [] # Abort execution cleanly returning an empty list

            # Temporarily reserve the ID to ensure 1-to-1 matching during validation
            matched_po_line_ids.append(matched_line.id)

        # --- STEP 2: GENERATE INVOICE LINES (Only reached if ALL lines matched) ---
        # Reset tracker for the actual mapping loop
        matched_po_line_ids = []

        for line in concept_nodes:
            quantity = float(line.get("Cantidad") or 1.0)
            description = line.get("Descripcion") or "Imported Line"
            unit_price = float(line.get("ValorUnitario") or 0.0)
            identification_no = line.get("NoIdentificacion") or False
            # Extract line subtotal from XML for the specialized matching function
            xml_subtotal = float(line.get("Importe") or 0.0)

            # Invoke the external function to find the matching PO line by subtotal, code, or name
            purchase_line = self._find_matching_purchase_line(
                po_lines=po_lines,
                xml_subtotal=xml_subtotal,
                matched_po_ids=matched_po_line_ids
            )
            # Search matching Odoo product
            # If a purchase order line was found, prioritize its product. Fallback to standard search if not.
            product = purchase_line.product_id if purchase_line else self.env['product.product'].browse()
            if not product and identification_no:
                product = self.env['product.product'].search([('default_code', '=', identification_no)], limit=1)
            if not product:
                product = self.env['product.product'].search([('name', 'ilike', description)], limit=1)

            # Register the matched purchase line ID to prevent it from being paired again
            if purchase_line:
                matched_po_line_ids.append(purchase_line.id)
            elif po_lines and product:
                purchase_line = po_lines.filtered(lambda l: l.product_id.id == product.id and l.id not in matched_po_line_ids)
                purchase_line = purchase_line[0] if purchase_line else False
                if purchase_line:
                    matched_po_line_ids.append(purchase_line.id)

            # DYNAMIC TAX EVALUATION STRATEGY
            if global_tax_ids:
                # Scenario A: Use the pre-calculated global taxes for every line
                line_tax_ids = global_tax_ids
            else:
                # Scenario B: Fallback to individual line item taxes from XML concept node
                line_tax_ids = self._get_xml_line_taxes(line, namespaces)

            line_vals = {
                'name': purchase_line.name if purchase_line else description,
                'quantity': quantity,
                'price_unit': unit_price,
                'product_id': product.id if product else False,
                'purchase_line_id': purchase_line.id if purchase_line else False,
                'tax_ids': [(6, 0, line_tax_ids)] if line_tax_ids else False,
                'x_xml_line_description': description,
                '_is_matched': True if purchase_line else False, # Flag used for downstream filtering
            }

            if product:
                # Extract the expense account directly from the product object since purchase_line lacks account_id
                account = product.product_tmpl_id._get_product_accounts()['expense']
                if account:
                    line_vals['account_id'] = account.id

            invoice_lines.append((0, 0, line_vals))

        return invoice_lines

    def _create_invoice_from_xml(self):
        """
        Main orchestrator for invoice creation. Invokes header and lines builder sub-functions.
        Synchronizes matching taxes (global or line-based) back to the Purchase Order lines.
        """
        self.ensure_one()
        if self.invoice_id:
            return self.invoice_id

        xml_content = base64.b64decode(self.xml_file)
        xml_doc = etree.fromstring(xml_content)
        namespaces = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}

        # Detect if XML brings Global Taxes first
        global_tax_ids = self._get_xml_global_taxes(xml_doc, namespaces)

        # Build Header and Lines (lines helper will handle the tax branching logic)
        invoice_vals = self._prepare_invoice_header()

        # 1. Fetch raw line structures
        raw_lines = self._prepare_invoice_lines(xml_doc, namespaces, global_tax_ids=global_tax_ids)

        # Guard Clause: If raw_lines is empty, it means _prepare_invoice_lines found a mismatch,
        # logged the specific error, and aborted. We must exit here to avoid duplicate logs.
        if not raw_lines:
            return False

        # 2. Extract only matching lines based on our temporary internal flag
        matched_lines = [line for line in raw_lines if line[2].get('_is_matched')]

        # 3. CONTROLLED SHUTDOWN: If no lines matched, log error states and exit gracefully without raising
        if not matched_lines:
            msg = _("Validation Error: No lines in the XML file matched any pending lines on the current Purchase Order.")
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'state': 'error',
                'validation_log': (self.validation_log or "") + f"\n{msg}"
            })
            return False

        # 4. Cleanup temporary flags from dictionary to prevent Odoo structure write crashes
        for line in matched_lines:
            if '_is_matched' in line[2]:
                del line[2]['_is_matched']

        # Inject validated lines subset into invoice payload
        invoice_vals['invoice_line_ids'] = matched_lines

        # Synchronize Taxes back to Purchase Order (PO) Lines
        if self.purchase_id:
            if global_tax_ids:
                # Scenario A: Batch apply global taxes to all PO lines directly
                for po_line in self.purchase_id.order_line:
                    po_line.write({'taxes_id': [(6, 0, global_tax_ids)]})
            else:
                # Scenario B: Map line-by-line concept taxes back to matching PO lines
                concept_nodes = xml_doc.xpath("//cfdi:Concepto", namespaces=namespaces)
                # Filter actively for purchase order lines that have not been fully invoiced yet
                po_lines = self.purchase_id.order_line.filtered(lambda l: l.qty_to_invoice > 0)
                matched_po_ids = []

                for line in concept_nodes:
                    identification_no = line.get("NoIdentificacion") or False
                    description = line.get("Descripcion") or ""
                    # Extract line subtotal from XML for the specialized matching function
                    xml_subtotal = float(line.get("Importe") or 0.0)

                    # Invoke the external function to find the matching PO line by subtotal, code, or name
                    po_line = self._find_matching_purchase_line(
                        po_lines=po_lines,
                        xml_subtotal=xml_subtotal,
                        description=description,
                        identification_no=identification_no,
                        matched_po_ids=matched_po_ids
                    )

                    if po_line:
                        # Register the matched purchase line ID to prevent duplicate matching tracking
                        matched_po_ids.append(po_line.id)
                        line_specific_taxes = self._get_xml_line_taxes(line, namespaces)
                        if line_specific_taxes:
                            po_line.write({'taxes_id': [(6, 0, line_specific_taxes)]})

        # Create Account Move (Vendor Bill)
        ctx = dict(self.env.context, default_purchase_id=self.purchase_id.id)
        invoice = self.env['account.move'].with_context(ctx).create(invoice_vals)

        # Automatically validate and post the invoice to the general ledger (Converts from Draft to Posted)
        invoice.action_post()

        self.write({'invoice_id': invoice.id})

        if self.purchase_id:
            self.purchase_id.invoice_ids = [(4, invoice.id)]

        msg = _("Vendor bill automatically created and CONFIRMED (Posted) successfully. Reference ID: %s") % invoice.name
        self.validation_log = (self.validation_log or "") + f"\n{msg}"

        return invoice

    def action_process_and_validate_invoice_xml(self):
        """
        Main Orchestrator Action.
        Executes sequentially extraction, internal validation, and SAT verification.
        """
        self.ensure_one()

        # STEP 1: XML Parsing & Structure Extraction
        try:
            xml_data = self._parse_and_extract_xml_data()
            if not xml_data:
                self.write({
                    'state': 'error',
                    'validation_log': _("Validation Error: XML parsing failed or the uploaded file is empty.")
                })
                return
        except Exception as e:
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'state': 'xml_error',
                'validation_log': _("XML Structure Validation Error (Invalid layout, encoding issues, or missing required CFDI nodes): %s") % str(e)
            })
            return

        # STEP 2: Purchase Order Header & Data Validation
        try:
            if not self.env.context.get('bypass_po_validation'):
                if not self._validate_purchase_order_data(
                    self.emisor_rfc,
                    self.receptor_rfc,
                    self.subtotal_amount,
                    self.sat_uuid,
                    xml_date=xml_data['xml_date'],
                ):
                    # Assumes _validate_purchase_order_data handles its own logs and returns False if invalid
                    return
            else:
                self.validation_log = _("Purchase Order validation bypassed via context parameters.")
        except Exception as e:
            self.write({
                'state': 'error',
                'validation_log': _("Purchase Order Validation Error (Critical failure while cross-referencing RFCs, amounts, or UUID against the system): %s") % str(e)
            })
            return

        # STEP 3: External SAT Web Service Request
        # Inside this method, requests.exceptions and HTTP codes are already safely caught
        self._request_sat_web_service(
            xml_data['xml_emisor_rfc'],
            xml_data['xml_receptor_rfc'],
            xml_data['xml_total'],
            xml_data['xml_uuid']
        )

        # STEP 4: Downstream Invoice Generation & Posting
        if self.cfdi_is_valid:
            try:
                self._create_invoice_from_xml()
            except Exception as e:
                self.write({
                    'state': 'error',
                    'validation_log': _("Invoice Generation Error (The XML and Purchase Order matched successfully, but vendor bill draft creation or validation workflow failed): %s") % str(e)
                })
                return

    def action_force_validate_xml_from_sat(self):
        """
        Executes the XML validation process forcing Odoo to skip
        internal Purchase Order checks, going directly to the SAT Web Service.
        """
        self.ensure_one()
        # Inject the context flag safely and execute the orchestrator method
        return self.with_context(bypass_po_validation=True).action_process_and_validate_invoice_xml()

    def action_draft(self):
        self.ensure_one()
        # Reset the current custom module record state back to draft
        self.write({'state': 'draft'})
        # Verify if there is an active linked invoice before executing operations
        if self.invoice_id:
            # If the invoice is already posted, invoke the native method to reset it to draft
            if self.invoice_id.state == 'posted':
                # Optional: Break any existing payment reconciliations during testing phases
                self.invoice_id.line_ids.remove_move_reconcile()
                # Native Odoo button method to change account.move state from 'posted' to 'draft'
                self.invoice_id.button_draft()
            # Once the invoice is safely in draft status, delete it from the database
            self.invoice_id.unlink()

    def _generate_cfdi_pdf_bytes(self):
        """
        Renders the vendor bill PDF using Odoo's QWeb report engine.
        Returns raw PDF bytes.
        """
        self.ensure_one()
        if not self.invoice_id:
            raise ValidationError(_("No vendor bill linked to this validator record."))

        report = self.env['ir.actions.report']._get_report_from_name('account.report_invoice')
        pdf_content, _content_type = report._render_qweb_pdf(
            report,
            res_ids=[self.invoice_id.id],
            data=None
        )
        return pdf_content
