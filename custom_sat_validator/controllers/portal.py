# -*- coding: utf-8 -*-
import base64
from lxml import etree
from odoo import http, _
from odoo.http import request
from odoo.addons.ike_event_purchase.controllers.portal import PurchaseOrderController


class PortalXmlValidator(http.Controller):

    @http.route('/my/purchase/validate_xml', type='json', auth='user', methods=['POST'])
    def portal_validate_xml(self, xml_file, filename, purchase_id, **kwargs):
        if not xml_file or not purchase_id:
            return {
                'success': False,
                'validation_log': "Missing XML file or Purchase Order reference."
            }

        # 1. Create the record explicitly binding the ID as an integer
        validator_record = request.env['custom.sat.validator'].sudo().create({
            'purchase_id': int(purchase_id),
            'xml_file': xml_file,
            'xml_filename': filename,
        })

        # 2. Force Odoo flush to ensure purchase_id is stored in the database transaction memory
        validator_record.flush_recordset()

        # 3. Execute the validation process using the newly created record's fields
        validator_record.action_process_and_validate_invoice_xml()

        return {
            'success': True,
            'state': validator_record.state,
            'sat_status': validator_record.sat_status,
            'validation_log': validator_record.validation_log,
            'uuid': validator_record.sat_uuid,
            'validator_id': validator_record.id,
            'tax_totals': validator_record.purchase_id.tax_totals if validator_record.purchase_id else False
        }

    @http.route('/my/purchase/download_cfdi_pdf2/<int:invoice_id>', type='http', auth='user', methods=['GET'])
    def download_cfdi_pdf2(self, invoice_id, **kwargs):

        invoice_id = request.env['account.move'].browse(invoice_id)

        pdf_bytes = invoice_id._generate_cfdi_pdf_bytes()
        filename = f"CFDI_{invoice_id.name}.pdf"

        return request.make_response(
            pdf_bytes,  # type: ignore
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', len(pdf_bytes)),
            ]
        )

    @http.route('/my/purchase/get_sat_validator_history', type='json', auth='user', methods=['POST'], website=True)
    def get_sat_validator_history(self, purchase_order_id, **kw):
        """
        Returns the audit log of uploaded/validated SAT document packages for a given purchase order,
        for display in the portal's history modal.
        """
        if not purchase_order_id:
            return {'success': False, 'error': 'Missing purchase order id.', 'lines': []}

        lines = request.env['custom.sat.validator.line'].sudo().search(
            [('validator_id.purchase_id', '=', int(purchase_order_id))],
            order='create_date desc',
        )

        return {
            'success': True,
            'lines': [{
                'id': line.id,
                'name': line.name,
                'sat_uuid': line.sat_uuid or '',
                'total_amount': line.total_amount,
                'sat_status': line.sat_status,
                'line_state': line.line_state,
                'invoice_id': line.invoice_id.id if line.invoice_id else False,
                'line_validation_log': line.line_validation_log or '',
            } for line in lines],
        }

    @http.route('/my/purchase/upload_sat_packages_queue', type='json', auth='user', methods=['POST'], website=True)
    def upload_sat_packages_queue(self, purchase_order_id, packages, **kw):
        """
        Receives the package queue from the portal, creates the root validator and its respective lines,
        and executes the atomic validation workflow for each one.
        """
        if not purchase_order_id or not packages:
            return {'success': False, 'error': 'Missing parameters or empty package queue.'}

        purchase_id = request.env['purchase.order'].sudo().browse(int(purchase_order_id))
        if not purchase_id.exists():
            return {'success': False, 'error': 'Purchase order not found.'}

        # 1. Create the master package (custom.sat.validator)
        validator_vals = {
            # 'name': f"Portal Package Match: {purchase_id.name}",
            'purchase_id': purchase_id.id,
        }
        validator_record = request.env['custom.sat.validator'].sudo().create(validator_vals)

        processed_count = 0

        # 2. Iterate over the queue received from Javascript and instantiate the lines
        for pkg in packages:
            line_vals = {
                'validator_id': validator_record.id,
                'xml_file': pkg.get('xml_file'),
                'xml_filename': pkg.get('xml_filename'),
                'pdf_file': pkg.get('pdf_file') or False,
                'pdf_filename': pkg.get('pdf_filename') or '',
                'carta_porte_file': pkg.get('carta_porte_file') or False,
            }

            # Create the line (automatically handles attachment persistence via the inherited create method)
            line_record = request.env['custom.sat.validator.line'].sudo().create(line_vals)

            # Immediately execute the validation workflow, PO auditing, SAT lookup, and invoicing
            line_record.action_process_line_workflow()
            processed_count += 1

        return {
            'success': True,
            'message': f"Successfully processed {processed_count} document packages for this order."
        }

    @http.route('/my/purchase/preview_sat_xml_lines', type='json', auth='user', website=True)
    def portal_preview_sat_xml_lines(self, purchase_order_id, xml_file, filename, **kw):
        """ Parse SAT CFDI XML file, execute validations/SAT WS, and return matched lines """
        if not purchase_order_id or not xml_file:
            return {'success': False, 'error': _('Purchase order or XML file was not provided.')}

        po = request.env['purchase.order'].sudo().browse(int(purchase_order_id))
        if not po.exists():
            return {'success': False, 'error': _('Purchase Order not found.')}

        try:
            # 1. Search for existing recent validator record or create a new one
            ValidatorModel = request.env['custom.sat.validator'].sudo()
            LineModel = request.env['custom.sat.validator.line'].sudo()

            validator_record = ValidatorModel.search([('purchase_id', '=', po.id)], order='id desc', limit=1)
            if not validator_record:
                validator_record = ValidatorModel.create({'purchase_id': po.id})

            val_line = LineModel.create({
                'validator_id': validator_record.id,
                'xml_file': xml_file,
                'xml_filename': filename,
            })

            # 2. Step 1: XML Parsing & Extraction
            xml_data = val_line._parse_and_extract_xml_data()
            if not xml_data:
                error_msg = val_line.line_validation_log or _("XML parsing failed.")
                return {'success': False, 'error': error_msg}

            # 3. Step 2: Run all Purchase Order validation rules
            po_valid = val_line._validate_purchase_order_data(
                val_line.emisor_rfc,
                val_line.receptor_rfc,
                val_line.subtotal_amount,
                val_line.sat_uuid,
                xml_date=xml_data.get('xml_date')
            )

            if not po_valid or val_line.line_state == 'xml_error':
                error_msg = val_line.line_validation_log or _("Purchase order validation failed.")
                return {'success': False, 'error': error_msg}

            # 4. Step 3: Web Service SAT Status Check
            sat_success = val_line._request_sat_web_service(
                xml_data['xml_emisor_rfc'],
                xml_data['xml_receptor_rfc'],
                xml_data['xml_total'],
                xml_data['xml_uuid']
            )

            if not sat_success or not val_line.cfdi_is_valid:
                error_msg = val_line.line_validation_log or _("SAT Status Verification Failed.")
                return {'success': False, 'error': error_msg}

            # 5. Map Purchase Order lines for client preview
            po_lines = po.order_line.filtered(lambda ln: not ln.display_type)
            result_lines = []

            for idx, po_line in enumerate(po_lines):
                xml_line_rec = val_line.xml_line_ids[idx] if idx < len(val_line.xml_line_ids) else False

                result_lines.append({
                    'po_line_id': po_line.id,
                    'po_product_name': po_line.product_id.display_name or po_line.name,
                    'po_qty': po_line.product_qty,
                    'po_subtotal': round(po_line.price_subtotal, 2),
                    'x_parent_expedient': po_line.x_parent_expedient or '',
                    'xml_folio': xml_data.get('xml_folio') or '',
                    'xml_product_name': xml_line_rec.product_name if xml_line_rec else '',
                    'xml_subtotal': round(xml_line_rec.subtotal, 2) if xml_line_rec else 0.0,
                })

            # Retain validator record and line history for auditing
            return {
                'success': True,
                'lines': result_lines
            }

        except Exception as e:
            return {'success': False, 'error': _('Error processing SAT XML file: %s') % str(e)}

    @http.route('/my/purchase/process_selected_sat_lines', type='json', auth='user', website=True)
    def process_selected_sat_lines(self, purchase_order_id, selected_po_line_ids, xml_file, xml_filename, pdf_file=False, pdf_filename=False, carta_porte_file=False, **kw):
        """ Creates the final validator line, executes SAT validation, and creates the vendor bill """
        if not purchase_order_id or not selected_po_line_ids or not xml_file:
            return {'success': False, 'error': _('Incomplete information or no lines were selected.')}

        po = request.env['purchase.order'].sudo().browse(int(purchase_order_id))
        if not po.exists():
            return {'success': False, 'error': _('Purchase Order not found.')}

        ValidatorModel = request.env['custom.sat.validator'].sudo()
        validator_record = ValidatorModel.search([('purchase_id', '=', po.id)], order='id desc', limit=1)

        if not validator_record:
            validator_record = ValidatorModel.create({'purchase_id': po.id})

        line_record = request.env['custom.sat.validator.line'].sudo().create({
            'validator_id': validator_record.id,
            'xml_file': xml_file,
            'xml_filename': xml_filename,
            'pdf_file': pdf_file or False,
            'pdf_filename': pdf_filename or '',
            'carta_porte_file': carta_porte_file or False,
        })

        # Execute complete line validation workflow (extraction, PO audit, SAT web service lookup, and invoicing)
        line_record.with_context(selected_po_line_ids=selected_po_line_ids).action_process_line_workflow()

        if line_record.invoice_id:
            return {
                'success': True,
                'message': _('Invoice successfully created and confirmed. Reference: %s') % line_record.invoice_id.name,
                'invoice_id': line_record.invoice_id.id,
            }
        else:
            return {
                'success': False,
                'error': line_record.line_validation_log or _('Invoice creation failed during SAT validation.')
            }


class PurchaseOrderControllerInherit(PurchaseOrderController):

    @http.route('/get_purchase_order_full_data', type='json', auth='user')
    def get_purchase_order_full_data(self, order_id):

        result = super().get_purchase_order_full_data(order_id)

        order = request.env['purchase.order'].sudo().browse(order_id)

        validator = request.env['custom.sat.validator'].sudo().search(
            [
                ('purchase_id', '=', order_id),
                # ('cfdi_is_valid', '=', True),
            ],
            order='id desc',
            limit=1
        )

        # Los impuestos se siguen tomando de la OC
        result['tax_totals'] = order.tax_totals

        # result['sat_status'] = validator.sat_status if validator else False
        # result['cfdi_is_valid'] = validator.cfdi_is_valid if validator else False
        result['validator_id'] = validator.id if validator else False

        return result
