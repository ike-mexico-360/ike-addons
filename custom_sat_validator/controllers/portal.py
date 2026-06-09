# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request


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
            'uuid': validator_record.sat_uuid
        }
