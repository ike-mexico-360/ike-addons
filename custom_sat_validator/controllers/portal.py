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


class PurchaseOrderControllerInherit(PurchaseOrderController):

    @http.route('/get_purchase_order_full_data', type='json', auth='user')
    def get_purchase_order_full_data(self, order_id):

        result = super().get_purchase_order_full_data(order_id)

        order = request.env['purchase.order'].sudo().browse(order_id)

        validator = request.env['custom.sat.validator'].sudo().search(
            [
                ('purchase_id', '=', order_id),
                ('cfdi_is_valid', '=', True),
            ],
            order='id desc',
            limit=1
        )

        # Los impuestos se siguen tomando de la OC
        result['tax_totals'] = order.tax_totals

        result['sat_status'] = validator.sat_status if validator else False
        result['cfdi_is_valid'] = validator.cfdi_is_valid if validator else False
        result['validator_id'] = validator.id if validator else False

        return result
