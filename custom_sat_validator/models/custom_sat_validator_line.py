# -*- coding: utf-8 -*-
import base64
import logging
import requests
from lxml import etree
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CustomSatValidatorLine(models.Model):
    _name = 'custom.sat.validator.line'
    _description = 'SAT Validator Document Package Line'
    _order = 'sequence, id'

    sequence = fields.Integer(string="Sequence", default=10)
    validator_id = fields.Many2one(
        'custom.sat.validator', string='Validator Reference', ondelete='cascade', required=True
    )

    name = fields.Char(string='Description / Invoice Folio', required=True, default='New Document Package')

    # Core Binary Fields
    xml_file = fields.Binary(string='XML File', required=True)
    xml_filename = fields.Char(string='XML Filename')
    pdf_file = fields.Binary(string='PDF File')
    pdf_filename = fields.Char(string='PDF Filename')
    carta_porte_file = fields.Binary(string='Carta Porte File')
    carta_porte_filename = fields.Char(string='Carta Porte Filename')

    # Relational persistence fields
    xml_attachment_id = fields.Many2one('ir.attachment', string='XML Attachment', ondelete='set null')
    pdf_attachment_id = fields.Many2one('ir.attachment', string='PDF Attachment', ondelete='set null')
    carta_porte_attachment_id = fields.Many2one('ir.attachment', string='Carta Porte Attachment', ondelete='set null')

    emisor_rfc = fields.Char(string="Issuer RFC", readonly=True)
    receptor_rfc = fields.Char(string="Receiver RFC", readonly=True)
    subtotal_amount = fields.Float(string="XML Subtotal", digits=(16, 2), readonly=True)
    total_amount = fields.Float(string="XML Total", digits=(16, 2), readonly=True)
    sat_uuid = fields.Char(string="UUID (Fiscal Folio)", readonly=True, index=True, copy=False)
    xml_invoice_date = fields.Date(string="XML Emission Date", readonly=True)

    sat_status = fields.Selection([
        ('Vigente', 'Active'),
        ('Cancelado', 'Cancelled'),
        ('No Encontrado', 'Not Found'),
        ('Error', 'Communication Error')
    ], string="SAT Status", readonly=True, default='No Encontrado', copy=False)

    cfdi_is_valid = fields.Boolean(string="Is XML Valid?", default=False, readonly=True)
    line_validation_log = fields.Text(string="Validation Log", readonly=True, copy=False)

    line_state = fields.Selection([
        ('draft', 'Draft'),
        ('xml_error', 'XML Mismatch / Error'),
        ('validated', 'Successfully Validated')
    ], string="Line Status", default='draft', readonly=True)

    invoice_id = fields.Many2one('account.move', string="Generated Vendor Bill", readonly=True, copy=False)

    xml_line_ids = fields.One2many(
        'custom.import.xml.invoice.line',
        'sat_line_id',
        string='XML Lines'
    )

    # --- ATOMIC ATTACHMENT SYNCHRONIZATION ---
    @api.model_create_multi
    def create(self, vals_list):
        records = super(CustomSatValidatorLine, self).create(vals_list)
        for record in records:
            record._create_or_update_attachments()
        return records

    def write(self, vals):
        res = super(CustomSatValidatorLine, self).write(vals)
        if any(f in vals for f in ['xml_file', 'pdf_file', 'carta_porte_file']):
            self._create_or_update_attachments()
        return res

    def _create_or_update_attachments(self):
        self.ensure_one()
        Attachment = self.env['ir.attachment'].sudo()
        file_mapping = [
            ('xml_file', 'xml_filename', 'xml_attachment_id'),
            ('pdf_file', 'pdf_filename', 'pdf_attachment_id'),
            ('carta_porte_file', 'carta_porte_filename', 'carta_porte_attachment_id'),
        ]
        for binary_field, name_field, attachment_field in file_mapping:
            file_data = getattr(self, binary_field)
            file_name = getattr(self, name_field) or 'document'
            current_attachment = getattr(self, attachment_field)

            if file_data:
                if current_attachment:
                    current_attachment.write({'datas': file_data, 'name': file_name})
                else:
                    new_attachment = Attachment.create({
                        'name': file_name,
                        'datas': file_data,
                        'res_model': self._name,
                        'res_id': self.id,
                    })
                    super(CustomSatValidatorLine, self).write({attachment_field: new_attachment.id})
            elif current_attachment and not file_data:
                current_attachment.unlink()

    # --- LOCAL WORKFLOW ORCHESTRATOR FOR THE LINE ---
    def action_process_line_workflow(self):
        """ Executes extraction, validation, web service, and invoicing for this line only """
        self.ensure_one()

        # STEP 1: XML Parsing & Structure Extraction
        try:
            xml_data = self._parse_and_extract_xml_data()
            if not xml_data:
                self.write({
                    'line_state': 'xml_error',
                    'line_validation_log': _("Validation Error: XML parsing failed or the uploaded file is empty.")
                })
                return
        except Exception as e:
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'line_state': 'xml_error',
                'line_validation_log': _("XML Structure Validation Error: %s") % str(e)
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
                    return
            else:
                self.line_validation_log = _("Purchase Order validation bypassed via context parameters.")
        except Exception as e:
            self.write({
                'line_state': 'xml_error',
                'line_validation_log': _("Purchase Order Validation Error: %s") % str(e)
            })
            return

        # STEP 3: External SAT Web Service Request
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
                    'line_state': 'xml_error',
                    'line_validation_log': _("Invoice Generation Error: %s") % str(e)
                })
                return

    def action_force_validate_xml_from_sat(self):
        """ Executes line process skipping parent PO matching rules """
        self.ensure_one()
        return self.with_context(bypass_po_validation=True).action_process_line_workflow()

    # --- ATOMIC VALIDATIONS ADAPTED TO LINE ---
    def _check_required_purchase_order(self):
        self.ensure_one()
        if not self.validator_id.purchase_id:
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("Validation Error: Selecting a Purchase Order is strictly mandatory to audit the XML.")
            })
            return False
        return True

    def _validate_sap_reference_received(self):
        self.ensure_one()
        sap_ref = self.validator_id.purchase_id.x_ref_sap
        is_empty = not sap_ref or not sap_ref.strip()
        is_string_false = sap_ref and sap_ref.strip().lower() == 'false'

        if is_empty or is_string_false:
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("Validation Error: The linked Purchase Order does not have a valid SAP reference configured.")
            })
            return False
        return True

    def _validate_duplicate_uuid(self, xml_uuid):
        if not xml_uuid:
            return True

        xml_uuid_upper = xml_uuid.upper()
        duplicate_bill = self.env['account.move'].search([
            ('x_xml_uuid', '=', xml_uuid_upper),
        ], limit=1)

        if duplicate_bill:
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("The XML UUID already exists in the system on invoice: %s.") % duplicate_bill.display_name
            })
            return False
        return True

    def _validate_receptor_rfc(self, xml_receptor_rfc):
        self.ensure_one()
        client_partner = self.validator_id.purchase_id.x_invoice_company_id

        # 1. Check if the Client field is defined on the Purchase Order
        if not client_partner:
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("Validation Error: The Purchase Order '%s' does not have a Client assigned.") % self.validator_id.purchase_id.name
            })
            return False

        company_rfc = client_partner.vat

        # 2. Check if the assigned Client has a configured RFC (VAT)
        if not company_rfc:
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("Validation Error: The Client '%s' configured in the Purchase Order does not have a RFC (VAT).") % client_partner.name
            })
            return False

        # 3. Compare XML Receiver RFC vs Purchase Order Client RFC
        if xml_receptor_rfc.strip().upper() != company_rfc.strip().upper():
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("XML Error: The XML receiver RFC (%s) does not match the Purchase Order Client RFC (%s - %s).") % (xml_receptor_rfc, company_rfc, client_partner.name)
            })
            return False
        return True

    def _validate_emisor_rfc(self, xml_emisor_rfc):
        self.ensure_one()
        partner_rfc = self.validator_id.purchase_id.partner_id.vat

        if not partner_rfc:
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("Validation Error: The supplier '%s' on the PO does not have an RFC configured.") % self.validator_id.purchase_id.partner_id.name
            })
            return False

        if xml_emisor_rfc.strip().upper() != partner_rfc.strip().upper():
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("XML Error: The Issuer RFC (%s) does not belong to the supplier assigned to the PO (%s).") % (xml_emisor_rfc, partner_rfc)
            })
            return False
        return True

    def _validate_total_amount(self, xml_subtotal):
        self.ensure_one()
        po_subtotal = self.validator_id.purchase_id.amount_untaxed

        if round(xml_subtotal, 2) > round(po_subtotal, 2):
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("XML Error: The XML subtotal ($%s) does not match the expected subtotal in the PO (%s).") % (round(xml_subtotal, 2), round(po_subtotal, 2))
            })
            return False
        return True

    def _validate_date_alignment(self, xml_date):
        self.ensure_one()
        if not self.validator_id.purchase_id:
            return False

        max_days = self.env.company.x_xml_max_days_old or 0
        po_date = self.validator_id.purchase_id.date_order.date() if self.validator_id.purchase_id.date_order else False

        if not po_date or not xml_date:
            return True

        if isinstance(xml_date, str):
            xml_date = fields.Date.from_string(xml_date)
        elif isinstance(xml_date, fields.Datetime):
            xml_date = xml_date.date()

        limit_date = po_date + timedelta(days=max_days)

        if limit_date < xml_date:
            message = _(
                "Date Error: The XML date (%s) exceeds the allowed threshold of "
                "%s day(s) after the Purchase Order creation date (%s). Maximum allowed date: %s."
            ) % (xml_date, max_days, po_date, limit_date)

            self.line_validation_log = (self.line_validation_log or "") + f"\n{message}"
            return False

        return True

    def _validate_purchase_order_data(self, xml_emisor_rfc, xml_receptor_rfc, xml_subtotal, xml_uuid, xml_date=False):
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

    def _process_xml_lines(self, xml_doc, namespaces):
        """ Extracts SAT CFDI XML lines (Conceptos) and registers them in custom.import.xml.invoice.line """
        self.ensure_one()

        # Unlink previous lines to avoid duplicated records on re-validation
        self.xml_line_ids.unlink()

        concept_nodes = xml_doc.xpath("//cfdi:Concepto", namespaces=namespaces)
        if not concept_nodes:
            return

        parent = self.validator_id
        po_lines = parent.purchase_id.order_line.filtered(lambda l: l.qty_to_invoice > 0) if parent.purchase_id else False
        matched_po_line_ids = []

        line_vals = []
        for line in concept_nodes:
            quantity = float(line.get("Cantidad") or 1.0)
            description = line.get("Descripcion") or "Imported Line"
            unit_price = float(line.get("ValorUnitario") or 0.0)
            xml_subtotal = float(line.get("Importe") or 0.0)

            # Extract line specific taxes
            line_taxes = self._get_xml_line_taxes(line, namespaces)

            # Match with Purchase Order Line if PO is linked
            matched_po_line = self._find_matching_purchase_line(
                po_lines=po_lines,
                xml_subtotal=xml_subtotal,
                matched_po_ids=matched_po_line_ids
            )
            matched_po_ids = []
            if matched_po_line:
                matched_po_line_ids.append(matched_po_line.id)
                matched_po_ids.append(matched_po_line.id)

            line_vals.append((0, 0, {
                'product_name': description,
                'quantity': quantity,
                'price_unit': unit_price,
                'subtotal': xml_subtotal,
                'tax_ids': [(6, 0, line_taxes)] if line_taxes else False,
                'purchase_order_line_ids': [(6, 0, matched_po_ids)] if matched_po_ids else False,
                'company_id': self.env.company.id,
            }))

        if line_vals:
            self.write({'xml_line_ids': line_vals})

    # --- PARSING AND EXTRACTION ---
    def _parse_and_extract_xml_data(self):
        self.ensure_one()
        if not self.xml_file:
            raise ValidationError(_("Please, upload an XML file."))

        if self.xml_filename and not self.xml_filename.lower().endswith('.xml'):
            raise ValidationError(_("The file must have an .xml extension."))

        xml_content = base64.b64decode(self.xml_file)
        xml_doc = etree.fromstring(xml_content)

        namespaces = {'cfdi': 'http://www.sat.gob.mx/cfd/4', 'tfd': 'http://www.sat.gob.mx/TimbreFiscalDigital'}

        emisor_node = xml_doc.xpath("//cfdi:Emisor", namespaces=namespaces)
        receptor_node = xml_doc.xpath("//cfdi:Receptor", namespaces=namespaces)
        timbre_node = xml_doc.xpath("//tfd:TimbreFiscalDigital", namespaces=namespaces)

        if not timbre_node:
            self.write({
                'line_state': 'xml_error',
                'cfdi_is_valid': False,
                'line_validation_log': _("Error: The XML does not contain the mandatory 'TimbreFiscalDigital' node.")
            })
            return False

        raw_fecha = xml_doc.get("Fecha") or xml_doc.get("fecha")
        extracted_date = False
        if raw_fecha:
            extracted_date = fields.Date.from_string(raw_fecha.split('T')[0])

        extracted_folio = xml_doc.get("Folio") or xml_doc.get("folio") or 'No Folio'
        extracted_emisor_rfc = emisor_node[0].get("Rfc") if emisor_node else False
        extracted_receptor_rfc = receptor_node[0].get("Rfc") if receptor_node else False
        xml_subtotal_float = float(xml_doc.get("SubTotal") or 0.0)
        xml_total_float = float(xml_doc.get("Total") or 0.0)
        extracted_uuid = timbre_node[0].get("UUID")

        # --- EXTRACT AND RECORD LINE DETAILS FROM XML ---
        self._process_xml_lines(xml_doc, namespaces)

        self.write({
            'name': extracted_folio,
            'emisor_rfc': extracted_emisor_rfc,
            'receptor_rfc': extracted_receptor_rfc,
            'total_amount': xml_total_float,
            'subtotal_amount': xml_subtotal_float,
            'sat_uuid': extracted_uuid,
            'xml_invoice_date': extracted_date,
        })

        return {
            'xml_folio': extracted_folio,
            'xml_emisor_rfc': extracted_emisor_rfc,
            'xml_receptor_rfc': extracted_receptor_rfc,
            'xml_subtotal': xml_subtotal_float,
            'xml_total': xml_total_float,
            'xml_uuid': extracted_uuid,
            'xml_date': extracted_date
        }

    # --- SAT WEB SERVICE ---
    def _request_sat_web_service(self, xml_emisor_rfc, xml_receptor_rfc, xml_total, xml_uuid):
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
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'line_state': 'xml_error',
                'line_validation_log': _("SAT Server Connectivity Error: %s") % str(connection_error)
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
                    'line_state': 'validated' if is_valid else 'xml_error',
                    'line_validation_log': _("Successful Parse.\nSAT Response Code: %s\nCurrent Status: %s.\n") % (codigo_res, status_res)
                })
                return True
            except Exception as parsing_soap_error:
                self.write({
                    'sat_status': 'Error',
                    'cfdi_is_valid': False,
                    'line_state': 'xml_error',
                    'line_validation_log': _("SAT Response Payload Parse Error: %s") % str(parsing_soap_error)
                })
                return False
        else:
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'line_state': 'xml_error',
                'line_validation_log': _("SAT Server Response Error (HTTP %s).") % response.status_code
            })
            return False

    # --- INVOICE GENERATION LOGIC ---
    def _prepare_invoice_header(self):
        self.ensure_one()
        parent = self.validator_id
        partner_id = parent.purchase_id.partner_id.id if parent.purchase_id else self.env['res.partner'].search([('vat', '=', self.emisor_rfc)], limit=1).id

        return {
            'move_type': 'in_invoice',
            'partner_id': partner_id,
            'invoice_origin': parent.purchase_id.name if parent.purchase_id else parent.name,
            'purchase_id': parent.purchase_id.id if parent.purchase_id else False,
            'currency_id': parent.purchase_id.currency_id.id if parent.purchase_id else self.env.company.currency_id.id,
            'invoice_date': fields.Date.context_today(self),
            'ref': self.name,
            'x_xml_uuid': self.sat_uuid.upper() if self.sat_uuid else False,
        }

    def _get_xml_global_taxes(self, xml_doc, namespaces):
        self.ensure_one()
        tax_ids = []
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

        concept_withholdings = xml_doc.xpath("//cfdi:Concepto/cfdi:Impuestos/cfdi:Retenciones/cfdi:Retencion", namespaces=namespaces)
        for withholding in concept_withholdings:
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

    def _get_xml_line_taxes(self, line_node, namespaces):
        self.ensure_one()
        tax_ids = []
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
        if not po_lines:
            return False
        for po_line in po_lines:
            if po_line.id in matched_po_ids:
                continue
            po_pending_subtotal = po_line.price_unit * po_line.qty_to_invoice
            if abs(po_pending_subtotal - xml_subtotal) <= tolerance:
                return po_line
        return False

    def _prepare_invoice_lines(self, xml_doc, namespaces, global_tax_ids=False):
        self.ensure_one()
        invoice_lines = []
        concept_nodes = xml_doc.xpath("//cfdi:Concepto", namespaces=namespaces)
        parent = self.validator_id
        po_lines = parent.purchase_id.order_line.filtered(lambda l: l.qty_to_invoice > 0) if parent.purchase_id else False
        matched_po_line_ids = []

        if not po_lines and concept_nodes:
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'line_state': 'xml_error',
                'line_validation_log': _("The Purchase Order has no pending lines to invoice, but XML contains items.")
            })
            return []

        for line in concept_nodes:
            xml_subtotal = float(line.get("Importe") or 0.0)
            description = line.get("Descripcion") or "Unknown item"
            matched_line = self._find_matching_purchase_line(
                po_lines=po_lines,
                xml_subtotal=xml_subtotal,
                matched_po_ids=matched_po_line_ids
            )
            if not matched_line:
                error_msg = _(
                    "Verification Failed: Mismatched Document Structure. The XML line '%(desc)s' with amount $%(amount).2f "
                    "could not be matched with any available line in the Purchase Order."
                ) % {'desc': description, 'amount': xml_subtotal}
                self.write({
                    'sat_status': 'Error',
                    'cfdi_is_valid': False,
                    'line_state': 'xml_error',
                    'line_validation_log': error_msg
                })
                return []
            matched_po_line_ids.append(matched_line.id)

        matched_po_line_ids = []
        for line in concept_nodes:
            quantity = float(line.get("Cantidad") or 1.0)
            description = line.get("Descripcion") or "Imported Line"
            unit_price = float(line.get("ValorUnitario") or 0.0)
            identification_no = line.get("NoIdentificacion") or False
            xml_subtotal = float(line.get("Importe") or 0.0)

            purchase_line = self._find_matching_purchase_line(
                po_lines=po_lines,
                xml_subtotal=xml_subtotal,
                matched_po_ids=matched_po_line_ids
            )
            product = purchase_line.product_id if purchase_line else self.env['product.product'].browse()
            if not product and identification_no:
                product = self.env['product.product'].search([('default_code', '=', identification_no)], limit=1)
            if not product:
                product = self.env['product.product'].search([('name', 'ilike', description)], limit=1)

            if purchase_line:
                matched_po_line_ids.append(purchase_line.id)
            elif po_lines and product:
                purchase_line = po_lines.filtered(lambda l: l.product_id.id == product.id and l.id not in matched_po_line_ids)
                purchase_line = purchase_line[0] if purchase_line else False
                if purchase_line:
                    matched_po_line_ids.append(purchase_line.id)

            line_tax_ids = global_tax_ids if global_tax_ids else self._get_xml_line_taxes(line, namespaces)

            line_vals = {
                'name': purchase_line.name if purchase_line else description,
                'quantity': quantity,
                'price_unit': unit_price,
                'product_id': product.id if product else False,
                'purchase_line_id': purchase_line.id if purchase_line else False,
                'tax_ids': [(6, 0, line_tax_ids)] if line_tax_ids else False,
                'x_xml_line_description': description,
                '_is_matched': True if purchase_line else False,
            }

            if product:
                account = product.product_tmpl_id._get_product_accounts()['expense']
                if account:
                    line_vals['account_id'] = account.id

            invoice_lines.append((0, 0, line_vals))

        return invoice_lines

    def _create_invoice_from_xml(self):
        self.ensure_one()
        if self.invoice_id:
            return self.invoice_id

        xml_content = base64.b64decode(self.xml_file)
        xml_doc = etree.fromstring(xml_content)
        namespaces = {'cfdi': 'http://www.sat.gob.mx/cfd/4'}

        global_tax_ids = self._get_xml_global_taxes(xml_doc, namespaces)
        invoice_vals = self._prepare_invoice_header()
        raw_lines = self._prepare_invoice_lines(xml_doc, namespaces, global_tax_ids=global_tax_ids)

        if not raw_lines:
            return False

        matched_lines = [line for line in raw_lines if line[2].get('_is_matched')]

        if not matched_lines:
            msg = _("Validation Error: No lines in the XML file matched any pending lines on the current Purchase Order.")
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'line_state': 'xml_error',
                'line_validation_log': (self.line_validation_log or "") + f"\n{msg}"
            })
            return False

        for line in matched_lines:
            if '_is_matched' in line[2]:
                del line[2]['_is_matched']

        invoice_vals['invoice_line_ids'] = matched_lines
        parent = self.validator_id

        ctx = dict(self.env.context, default_purchase_id=parent.purchase_id.id)
        invoice = self.env['account.move'].with_context(ctx).create(invoice_vals)

        for line in invoice.invoice_line_ids:
            if line.purchase_line_id and line.tax_ids:
                line.purchase_line_id.write({
                    'taxes_id': [(6, 0, line.tax_ids.ids)]
                })

        self.write({'invoice_id': invoice.id})

        if parent.purchase_id:
            parent.purchase_id.invoice_ids = [(4, invoice.id)]

        msg = _("Vendor bill automatically created and CONFIRMED (Posted) successfully. Reference ID: %s") % invoice.name
        self.line_validation_log = (self.line_validation_log or "") + f"\n{msg}"

        return invoice

    # --- RESET TO DRAFT & HELPER ---
    def action_reset_to_draft(self):
        """ Resets line log states and removes invoice dependencies cleanly """
        self.ensure_one()
        if self.invoice_id:
            if self.invoice_id.state == 'posted':
                self.invoice_id.button_draft()
            self.invoice_id.unlink()
        self.write({
            'line_state': 'draft',
            'sat_status': 'No Encontrado',
            'cfdi_is_valid': False,
            'line_validation_log': False
        })

    def _generate_cfdi_pdf_bytes(self):
        self.ensure_one()
        if not self.invoice_id:
            raise ValidationError(_("No vendor bill linked to this validator record."))
        report = self.env['ir.actions.report']._get_report_from_name('account.report_invoice')
        pdf_content, _content_type = report._render_qweb_pdf(report, res_ids=[self.invoice_id.id], data=None)
        return pdf_content
