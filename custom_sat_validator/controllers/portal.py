# -*- coding: utf-8 -*-
from odoo import http
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
        import logging
        _logger = logging.getLogger(__name__)
        _logger.warning("=== CFDI PDF DEBUG ===")
        _logger.warning("invoice_id recibido: %s", invoice_id)

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
