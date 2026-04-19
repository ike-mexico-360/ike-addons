from odoo import http
from odoo.http import request
from odoo.addons.purchase.controllers.portal import CustomerPortal as PurchasePortal

from odoo.exceptions import AccessError, MissingError
from odoo.tools.translate import _
import logging
_logger = logging.getLogger(__name__)


class CustomerPortal(PurchasePortal):

    items_per_page = 2

    # Contar solo los rfq's del proveedoral que pertenece el usuario
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        PurchaseOrder = request.env['purchase.order']

        user_id = request.env.user
        request.env.cr.execute("""
            SELECT supplier_id AS id
            FROM res_partner_supplier_users_rel
            WHERE user_id = %s
        """, (user_id.id,))
        result = request.env.cr.fetchone()
        if 'rfq_count' in counters:
            values['rfq_count'] = PurchaseOrder.search_count([
                ('partner_id', '=', result[0]),
                ('x_dispute_state', 'not in', ['open', 'submitted']),
                ('state', 'in', ['sent'])
            ]) or 1 if PurchaseOrder.has_access('read') else 0

        return values

    # Mostrar solo las rfq's del proveedor que pertenece al usuario
    def _render_portal(
            self, template, page, date_begin, date_end, sortby, filterby, domain, searchbar_filters, default_filter,
            url, history, page_name, key):

        if page_name == 'rfq':
            user_id = request.env.user
            request.env.cr.execute("""
                SELECT supplier_id AS id
                FROM res_partner_supplier_users_rel
                WHERE user_id = %s
            """, (user_id.id,))
            result = request.env.cr.fetchone()

            domain += [('partner_id', '=', result[0]), ('x_dispute_state', 'not in', ['open', 'submitted'])]

        return super()._render_portal(
            template, page, date_begin, date_end, sortby,
            filterby, domain, searchbar_filters, default_filter,
            url, history, page_name, key
        )

    @http.route(['/my/rfq', '/my/rfq/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_requests_for_quotation(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        return self._render_portal(
            "purchase.portal_my_purchase_rfqs",
            page, date_begin, date_end, sortby, filterby,
            [('state', 'in', ['sent', 'to_consolidate', 'consolidated'])],
            {},
            None,
            "/my/rfq",
            'my_rfqs_history',
            'rfq',
            'rfqs'
        )

    @http.route(['/my/purchase', '/my/purchase/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_purchase_orders(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        self._items_per_page = 10
        search = kw.get('search', '').strip()
        base_domain = [('name', 'ilike', search)] if search else []
        return self._render_portal(
            "purchase.portal_my_purchase_orders",
            page, date_begin, date_end, sortby, filterby,
            base_domain,
            {
                'all': {'label': _('All'), 'domain': [('state', 'in', ['purchase', 'done', 'cancel'])]},
                'purchase': {'label': _('Purchase Order'), 'domain': [('state', '=', 'purchase')]},
                'cancel': {'label': _('Cancelled'), 'domain': [('state', '=', 'cancel')]},
                'done': {'label': _('Locked'), 'domain': [('state', '=', 'done')]},
            },
            'all',
            "/my/purchase",
            'my_purchases_history',
            'purchase',
            'orders'
        )

    @http.route(['/my/purchase/<int:order_id>'], type='http', auth="public", website=True)
    def portal_my_purchase_order(self, order_id=None, access_token=None, **kw):
        # Disputa
        dispute_type = kw.get('dispute')
        if dispute_type in ('accept', 'decline'):
            try:
                order_sudo = self._document_check_access('purchase.order', order_id, access_token=access_token)
            except (AccessError, MissingError):
                return request.redirect('/my')

            if dispute_type == 'accept':
                order_sudo.x_action_approve_dispute()
            elif dispute_type == 'decline':
                order_sudo.x_action_reject_dispute()

            # Redirige al mismo portal sin el parámetro dispute
            return request.redirect(f'/my/purchase/{order_id}?access_token={access_token or ""}')

        # Para todo lo demás, comportamiento original
        return super().portal_my_purchase_order(order_id=order_id, access_token=access_token, **kw)

    @http.route(['/my/purchase/<int:order_id>/dispute'], type='http', auth="public", website=True)
    def portal_my_purchase_order_dispute(self, order_id=None, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access('purchase.order', order_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        # Disputa
        dispute_type = kw.get('dispute')
        values = {
            'order_sudo': order_sudo,
            'page_name': 'po_dispute',
            'dispute': dispute_type,
        }
        return request.render('ike_event_purchase.ike_event_purchase_dispute_view', values)

        # Redirige al mismo portal sin el parámetro dispute
        # return request.redirect(f'/my/purchase/{order_id}?access_token={access_token or ""}')

    @http.route(
        ["/my/purchase/<int:product_id>/get_matrix_lines"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def x_ike_my_purchase_product_get_matrix_lines(self, product_id, event_id, supplier_id, **kw):
        try:
            matrix_lines = request.env['ike.event'].sudo().browse(event_id)\
                .get_supplier_product_matrix_lines(supplier_id, [product_id])
            _logger.warning(f"matrix_lines: {matrix_lines}")
            return {"success": True, "matrix_lines": matrix_lines.read(['cost'])}
        except Exception as e:
            _logger.error(f"Error at get_supplier_product_matrix_lines: {str(e)}")
            return {"success": False, "message": str(e)}
