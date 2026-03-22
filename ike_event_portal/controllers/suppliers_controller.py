# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

# from collections import OrderedDict

from odoo import http
# from odoo.osv import expression
from odoo.addons.portal.controllers.portal import CustomerPortal  # , pager as portal_pager
# from odoo.addons.account.controllers.download_docs import _get_headers, _build_zip_from_data
from odoo.exceptions import AccessError, MissingError
from odoo.http import request


class PortalAccount(CustomerPortal):

    def _get_ike_event_suppliers_domain(self):
        return []

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'ike_event_supplier_count' in counters:
            values['ike_event_supplier_count'] = request.env['res.partner'].search_count(self._get_ike_event_suppliers_domain(), limit=1)
        return values

    # Lista de proveedores
    @http.route(['/event/portal/suppliers', '/event/portal/suppliers/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_invoices(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        suppliers = request.env['res.partner'].search(self._get_ike_event_suppliers_domain())

        values = {
            'suppliers': suppliers,
        }
        return request.render("ike_event_portal.portal_ike_event_suppliers", values)

    # Vista de un proveedor
    @http.route(['/event/portal/supplier/<int:supplier_id>'], type='http', auth="public", website=True)
    def portal_my_invoice_detail(self, supplier_id, access_token=None, report_type=None, download=False, **kw):
        try:
            self._document_check_access('res.partner', supplier_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        values = {
            'supplier': request.env['res.partner'].browse(supplier_id),
        }
        return request.render("ike_event_portal.portal_ike_event_supplier_view", values)

    # Route to display the creation form
    @http.route(['/event/portal/supplier/new'], type='http', auth="user", website=True)
    def portal_new_supplier(self, **kw):
        # Fetch potential drivers for the dropdown
        drivers = request.env['res.partner'].search([])
        values = {
            'drivers': drivers,
            'page_name': 'new_supplier',
        }
        return request.render("ike_event_portal.portal_create_supplier", values)

    # Route to process the form submission
    @http.route(['/event/portal/supplier/create'], type='http', auth="user", website=True, methods=['POST'])
    def portal_create_supplier(self, **kw):
        # Prepare values for creation
        vals = {
            'name': kw.get('name'),
            'email': kw.get('email'),
            'vehicle_registration': kw.get('vehicle_registration'),
            'vehicle_model': kw.get('vehicle_model'),
            'vehicle_type': kw.get('vehicle_type'),
            'service': kw.get('service'),
            'status': kw.get('status'),
            # Handle Many2one field safely
            'assigned_driver_id': int(kw.get('assigned_driver_id')) if kw.get('assigned_driver_id') else False,
        }

        # Create the new partner record
        new_supplier = request.env['res.partner'].create(vals)

        # Redirect to the new supplier's detail page
        return request.redirect('/event/supplier/%s' % new_supplier.id)
