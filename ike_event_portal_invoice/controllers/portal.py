from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request


class PortalInvoice(CustomerPortal):

    @http.route(
        ['/provider/portal/invoice/dian'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_invoice_dian(self, **kw):
        if not request.env.user.has_group('ike_event_portal.custom_group_portal_finance'):
            return request.redirect('/my')

        return request.redirect('/my/invoices?filterby=bills')
