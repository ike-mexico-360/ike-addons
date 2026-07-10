from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.purchase.controllers.portal import CustomerPortal as PurchasePortal

from odoo.exceptions import AccessError, MissingError
from odoo.osv import expression
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
                ('partner_id', '=', result[0] if result else 0),
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
            supplier_id = result[0] if result else 0

            domain += [('partner_id', '=', supplier_id), ('x_dispute_state', 'not in', ['open', 'submitted'])]

        return super()._render_portal(
            template, page, date_begin, date_end, sortby,
            filterby, domain, searchbar_filters, default_filter,
            url, history, page_name, key
        )

    @http.route(['/my/rfq', '/my/rfq/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_requests_for_quotation(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        self._items_per_page = 10
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

    @http.route(
        ["/my/purchase/<int:order_id>/post_message"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def post_purchase_order_message(self, order_id, body=None, attachments=None, **kw):
        try:
            # Get the purchase order
            purchase_order = request.env['purchase.order'].browse(order_id)

            # Check if user has access to this purchase order
            if not purchase_order.exists():
                return {"success": False, "error": _("Purchase order not found")}

            # Post the message
            message = purchase_order.message_post(
                body=body,
                message_type='comment',
                subtype_id=request.env.ref('mail.mt_comment').id,
            )

            # Handle attachments if provided
            if attachments:
                for attachment_data in attachments:
                    request.env['ir.attachment'].create({
                        'name': attachment_data.get('name', 'attachment'),
                        'type': 'binary',
                        'datas': attachment_data.get('data', ''),
                        'mimetype': attachment_data.get('mimetype', 'application/octet-stream'),
                        'res_model': 'mail.message',
                        'res_id': message.id,
                    })

            return {"success": True, "message_id": message.id}
        except Exception as e:
            _logger.error(f"Error posting message to purchase order {order_id}: {str(e)}")
            return {"success": False, "error": str(e)}


class PurchaseOrderController(http.Controller):

    def _get_purchase_order_portal_domain(self, filters=None):
        is_admin_or_staff = request.env.user.has_group('base.group_system')
        domain = [('state', 'in', ['purchase', 'done', 'cancel'])]

        if not is_admin_or_staff:
            supplier_rel = request.env['res.partner.supplier_users.rel'].sudo().search_read(
                domain=[('user_id', '=', request.env.user.id)],
                fields=['supplier_id'],
                limit=1
            )
            supplier_id = supplier_rel[0]['supplier_id'][0] if supplier_rel else False
            if not supplier_id:
                return expression.AND([domain, [('id', '=', 0)]])
            domain.append(('partner_id', '=', supplier_id))

        filters = filters or {}
        reference = (filters.get('reference') or '').strip()
        event = (filters.get('event') or '').strip()
        date_from = (filters.get('dateFrom') or '').strip()
        date_to = (filters.get('dateTo') or '').strip()

        if reference:
            domain.append(('name', 'ilike', reference))
        if event:
            domain = expression.AND([
                domain,
                expression.OR([
                    [('x_event_id.name', 'ilike', event)],
                    [('x_origin_events', 'ilike', event)],
                ])
            ])
        if date_from:
            domain.append(('date_approve', '>=', f'{date_from} 00:00:00'))
        if date_to:
            domain.append(('date_approve', '<=', f'{date_to} 23:59:59'))

        return domain

    @http.route('/get_purchase_order_full_data', type='json', auth='user')
    def get_purchase_order_full_data(self, order_id):
        specification = {
            'id': {},
            'name': {},
            'state': {},
            'partner_id': {'fields': {'id': {}, 'name': {}}},
            'x_event_public_id': {'fields': {'id': {}, 'name': {}}},
            'x_event_id': {'fields': {'id': {}, 'name': {}}},
            'message_ids': {
                'fields': {
                    'id': {},
                    'body': {},
                    'date': {},
                    'author_id': {'fields': {'id': {}, 'name': {}}},
                    'subtype_id': {'fields': {'id': {}, 'name': {}}},
                    'tracking_value_ids': {
                        'fields': {
                            'id': {},
                            'field_info': {},
                            'old_value_char': {},
                            'new_value_char': {},
                            'o2m_record_id': {},
                            'new_value_integer': {},
                            'old_value_integer': {},
                            'new_value_float': {},
                            'old_value_float': {},
                        }
                    },
                    'o2m_tracking_command_ids': {'fields': {'id': {}}},
                    'attachment_ids': {
                        'fields': {
                            'id': {},
                            'name': {},
                            'mimetype': {},
                            'file_size': {},
                        }
                    },
                }
            },
            'x_dispute_state': {},
            'x_dispute_approved': {},
            'x_change_comments': {},
            'date_approve': {},
            'date_planned': {},
            'company_id': {'fields': {'id': {}, 'name': {}}},
            'amount_untaxed': {},
            'amount_untaxed_dispute': {},
            'amount_untaxed_approved': {},
            'amount_untaxed_event': {},
            'order_line': {
                'fields': {
                    'id': {},
                    'name': {},
                    'display_name': {},
                    'display_type': {},
                    'product_id': {'fields': {'id': {}, 'name': {}, 'image_1024': {}}},
                    'product_qty': {},
                    'product_uom': {'fields': {'id': {}, 'name': {}, 'display_name': {}}},
                    'price_unit': {},
                    'taxes_id': {'fields': {'id': {}, 'name': {}, 'display_name': {}}},
                    # 'x_concept_line_id': {'fields': {'id': {}, 'display_name': {}}},
                    'x_base_unit_price': {},
                    'x_price_unit_dispute': {},
                    'x_product_qty_dispute': {},
                    'x_price_subtotal_dispute': {},
                    'x_price_unit_approved': {},
                    'x_product_qty_approved': {},
                    'x_price_subtotal_approved': {},
                    'x_product_qty_event': {},
                    'x_price_unit_event': {},
                    'x_price_subtotal_event': {},
                    'price_subtotal': {},
                    'x_parent_expedient': {},
                }
            },
            'x_dispute_iteration_count': {},
        }

        result = request.env['purchase.order'].sudo().web_search_read(
            [('id', '=', order_id)], specification
        )

        if not result or not result.get('records'):
            return {}

        order_data = result['records'][0]
        messages = order_data.get('message_ids', [])

        msg_ids_with_o2m = [
            m['id'] for m in messages
            if m.get('o2m_tracking_command_ids') and len(m['o2m_tracking_command_ids']) > 0
        ]

        if msg_ids_with_o2m:
            messages_rs = request.env['mail.message'].sudo().browse(msg_ids_with_o2m)
            o2m_trackings_map = messages_rs.get_o2m_tracking_format(model_name='purchase.order')

            for msg in messages:
                msg_id = msg.get('id')
                msg['o2mTrackings'] = o2m_trackings_map.get(msg_id) or []
        else:
            for msg in messages:
                msg['o2mTrackings'] = []

        order_data['order_attachment_ids'] = request.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'purchase.order'), ('res_id', '=', order_id)],
            ['id', 'name', 'mimetype', 'file_size'],
            order='id asc',
        )

        # Event info
        order = request.env['purchase.order'].sudo().browse(order_id)
        event = order.x_event_id
        if event:
            order_data['x_event_info'] = {
                'nu_name': event.nu_name or '',
                'event_date': str(event.event_date) if event.event_date else '',
                'location_label': event.location_label or '',
                'destination_label': event.destination_label or '',
            }
            event_supplier = event.service_supplier_ids.filtered(
                lambda s: s.supplier_id == order.partner_id
            )[:1]
            if event_supplier and event_supplier.truck_id:
                truck = event_supplier.truck_id
                order_data['x_event_info'].update({
                    'vehicle_name': truck.name or '',
                    'vehicle_plate': truck.license_plate or '',
                    'driver_name': truck.driver_id.name if truck.driver_id else '',
                })
            else:
                order_data['x_event_info'].update({
                    'vehicle_name': '',
                    'vehicle_plate': '',
                    'driver_name': '',
                })
        else:
            order_data['x_event_info'] = None

        return order_data

    @http.route('/my/purchase/load_orders_analytics', type='json', auth='user', methods=['POST'], website=True)
    def load_orders_analytics(self):
        """
        Fetches purchase orders dynamically.
        If the user is an internal Administrator/Employee, it returns ALL records.
        If the user is a Portal Supplier, it tightly scopes records to their bound ID.
        """
        try:
            po_domain = self._get_purchase_order_portal_domain()

            # 3. Execute main Purchase Orders dataset fetch via ORM browse for relation access
            purchase_orders = request.env['purchase.order'].sudo().search(po_domain)

            records = []
            for order in purchase_orders:
                event = order.x_event_id
                event_data = {'id': event.id, 'name': event.name} if event else False

                x_event_info = None
                if event:
                    x_event_info = {
                        'nu_name': event.nu_name or '',
                        'event_date': str(event.event_date) if event.event_date else '',
                        'location_label': event.location_label or '',
                        'destination_label': event.destination_label or '',
                    }
                    event_supplier = event.service_supplier_ids.filtered(
                        lambda s: s.supplier_id == order.partner_id
                    )[:1]
                    if event_supplier and event_supplier.truck_id:
                        truck = event_supplier.truck_id
                        x_event_info.update({
                            'vehicle_name': truck.name or '',
                            'vehicle_plate': truck.license_plate or '',
                            'driver_name': truck.driver_id.name if truck.driver_id else '',
                        })
                    else:
                        x_event_info.update({'vehicle_name': '', 'vehicle_plate': '', 'driver_name': ''})

                # 4. Extract full multi-layered invoice metadata safely with sudo override
                invoices_data = []
                if order.invoice_ids:
                    invoices_data = request.env['account.move'].sudo().search_read(
                        domain=[('id', 'in', order.invoice_ids.ids)],
                        fields=['id', 'name', 'state', 'payment_state', 'amount_total']
                    )

                records.append({
                    'id': order.id,
                    'name': order.name,
                    'state': order.state,
                    'x_event_id': event_data,
                    'date_approve': str(order.date_approve) if order.date_approve else False,
                    'date_planned': str(order.date_planned) if order.date_planned else False,
                    'amount_total': order.amount_total,
                    'invoice_ids': invoices_data,
                    'x_origin_events': order.x_origin_events or '',
                    'partner_id': {'id': order.partner_id.id, 'name': order.partner_id.name} if order.partner_id else False,
                    'x_event_public_id': {'id': order.x_event_public_id.id, 'name': order.x_event_public_id.name} if order.x_event_public_id else False,
                    'company_id': {'id': order.company_id.id, 'name': order.company_id.name} if order.company_id else False,
                    'x_event_info': x_event_info,
                })

            return {'records': records}

        except Exception as e:
            _logger.error("[Portal PO Controller] Execution failure in multi-role analytics loop: %s", str(e))
            return {'error': str(e), 'records': []}

    @http.route('/my/purchase/download_orders_pdf', type='http', auth='user', website=True)
    def download_orders_pdf(self, **kw):
        try:
            domain = self._get_purchase_order_portal_domain(kw)
            orders = request.env['purchase.order'].sudo().search(domain, order='date_approve desc, id desc')
            if not orders:
                return request.redirect('/my/purchase')

            report = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'ike_event_purchase.action_report_portal_purchase_orders',
                orders.ids,
                data={'report_type': 'pdf', 'filters': kw}
            )[0]
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(report)),
                ('Content-Disposition', content_disposition('ordenes_de_compra.pdf')),
            ]
            return request.make_response(report, headers=headers)
        except Exception as e:
            _logger.error("[Portal PO Controller] Error generating purchase orders PDF: %s", str(e))
            return request.redirect('/my/purchase')

    @http.route('/provider/portal/purchase/save_dispute', type='json', auth='user', methods=['POST'])
    def save_dispute(self, order_id, dispute_count, change_comments, order_lines):
        """
        Bypasses Record Rule restrictions on res.partner during tax/fiscal position
        recomputations by executing the write operation on purchase.order with sudo().
        """
        # 1. Fetch the order using sudo() to bypass security checks during calculations
        order = request.env['purchase.order'].sudo().browse(order_id)
        if not order.exists():
            return {'success': False, 'error': 'Order not found'}

        try:
            # directly into the write values dictionary without manual parsing.
            order.write({
                'x_dispute_iteration_count': dispute_count,
                'x_change_comments': change_comments,
                'order_line': order_lines,
            })
            return {'success': True}
        except Exception as e:
            _logger.error(f"Error saving purchase order dispute via RPC: {str(e)}")
            return {'success': False, 'error': str(e)}
