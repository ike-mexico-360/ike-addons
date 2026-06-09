# -*- coding: utf-8 -*-
import base64
import requests
from lxml import etree
from xml.etree import ElementTree as ET
from odoo import models, fields, api
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

    xml_file = fields.Binary(string="CFDI XML File", required=True, copy=False)
    xml_filename = fields.Char(string="XML File Name")

    emisor_rfc = fields.Char(string="Issuer RFC", readonly=True, index=True)
    receptor_rfc = fields.Char(string="Receiver RFC", readonly=True)
    total_amount = fields.Float(string="XML Total", digits=(16, 2), readonly=True)
    sat_uuid = fields.Char(string="UUID (Fiscal Folio)", readonly=True, index=True, copy=False)

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
        print("self.purchase_id", self.purchase_id)
        if not self.purchase_id:
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': "Validation Error: Selecting a Purchase Order is strictly mandatory to audit the XML."
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
                'validation_log': f"Validation Error: Your active company '{self.env.company.name}' does not have an RFC (VAT) configured in Odoo."
            })
            return False

        if xml_receptor_rfc.strip().upper() != company_rfc.strip().upper():
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': f"XML Error: The XML receiver RFC ({xml_receptor_rfc}) does not match your company RFC ({company_rfc}). The supplier invoiced a different entity."
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
                'validation_log': f"Odoo Error: The supplier '{self.purchase_id.partner_id.name}' on the PO does not have an RFC configured in their contact profile."
            })
            return False

        if xml_emisor_rfc.strip().upper() != partner_rfc.strip().upper():
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': f"XML Error: The Issuer RFC ({xml_emisor_rfc}) does not belong to the supplier assigned to the Purchase Order ({partner_rfc} - {self.purchase_id.partner_id.name})."
            })
            return False
        return True

    def _validate_total_amount(self, xml_total):
        """ Validates XML Total Amount against Purchase Order Total Amount """
        self.ensure_one()
        po_total = self.purchase_id.amount_total

        if round(xml_total, 2) != round(po_total, 2):
            self.write({
                'state': 'xml_error',
                'cfdi_is_valid': False,
                'validation_log': f"XML Error: The XML total (${round(xml_total, 2)}) does not match the expected total in the Purchase Order ({round(po_total, 2)})."
            })
            return False
        return True

    def _validate_purchase_order_data(self, xml_emisor_rfc, xml_receptor_rfc, xml_total):
        """
        Orchestrator method for internal business rules.
        Invokes atomic validations sequentially.
        """
        self.ensure_one()

        if not self._check_required_purchase_order():
            return False

        if not self._validate_receptor_rfc(xml_receptor_rfc):
            return False

        if not self._validate_emisor_rfc(xml_emisor_rfc):
            return False

        if not self._validate_total_amount(xml_total):
            return False

        return True

    def _parse_and_extract_xml_data(self):
        """
        Reads, decodes, and parses the binary XML file.
        Extracts structural attributes and writes them to the record.
        """
        self.ensure_one()
        if not self.xml_file:
            raise ValidationError("Please, upload an XML file.")

        if self.xml_filename and not self.xml_filename.lower().endswith('.xml'):
            raise ValidationError("The file must have an .xml extension.")

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
                'validation_log': "Error: The XML does not contain the mandatory 'TimbreFiscalDigital' node."
            })
            return False

        extracted_emisor_rfc = emisor_node[0].get("Rfc") if emisor_node else False
        extracted_receptor_rfc = receptor_node[0].get("Rfc") if receptor_node else False
        total_str = xml_doc.get("Total")
        extracted_uuid = timbre_node[0].get("UUID")

        xml_total_float = float(total_str or 0.0)

        self.write({
            'emisor_rfc': extracted_emisor_rfc,
            'receptor_rfc': extracted_receptor_rfc,
            'total_amount': xml_total_float,
            'sat_uuid': extracted_uuid
        })

        return {
            'xml_emisor_rfc': extracted_emisor_rfc,
            'xml_receptor_rfc': extracted_receptor_rfc,
            'xml_total': xml_total_float,
            'xml_uuid': extracted_uuid
        }

    def _request_sat_web_service(self, xml_emisor_rfc, xml_receptor_rfc, xml_total, xml_uuid):
        """
        Prepares the SOAP envelope, sends the POST request to SAT Web Service,
        and parses the response status.
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

        response = requests.post(soap_url, data=soap_xml, headers=headers, timeout=10)

        if response.status_code == 200:
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
                'validation_log': f"Successful Parse.\nSAT Response Code: {codigo_res}\nCurrent Status: {status_res}"
            })
            return True
        else:
            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'state': 'error',
                'validation_log': f"SAT Server Response Error. HTTP Code: {response.status_code}"
            })
            return False

    def action_process_and_validate_invoice_xml(self):
        """
        Main Orchestrator Action.
        Executes sequentially extraction, internal validation, and SAT verification.
        """
        self.ensure_one()

        try:
            print("33333")
            xml_data = self._parse_and_extract_xml_data()
            if not xml_data:
                return

            print("222222")
            if not self._validate_purchase_order_data(
                xml_data['xml_emisor_rfc'],
                xml_data['xml_receptor_rfc'],
                xml_data['xml_total']
            ):
                return
            print("11111")
            self._request_sat_web_service(
                xml_data['xml_emisor_rfc'],
                xml_data['xml_receptor_rfc'],
                xml_data['xml_total'],
                xml_data['xml_uuid']
            )
            print("4444")

        except Exception as e:
            print("5555555")

            self.write({
                'sat_status': 'Error',
                'cfdi_is_valid': False,
                'state': 'error',
                'validation_log': f"General Critical Processing Error: {str(e)}"
            })
