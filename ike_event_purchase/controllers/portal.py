import io
import logging

import xlsxwriter

from odoo import http
from odoo.http import request, content_disposition
from odoo.addons.purchase.controllers.portal import CustomerPortal as PurchasePortal

from odoo.exceptions import AccessError, MissingError
from odoo.osv import expression
from odoo.tools.translate import _
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
                .get_supplier_product_matrix_lines_by_supplier(supplier_id, [product_id])
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

    @http.route(
        ["/my/purchase/<int:order_id>/upload_files"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def upload_purchase_order_files(self, order_id, attachments=None, **kw):
        ALLOWED_MIMETYPES = {'application/pdf', 'image/png', 'image/jpeg'}
        MAX_SIZE = 3 * 1024 * 1024
        MAX_FILES = 2
        try:
            purchase_order = request.env['purchase.order'].browse(order_id)
            if not purchase_order.exists():
                return {"success": False, "error": _("Purchase order not found")}

            attachments = attachments or []
            existing_count = request.env['ir.attachment'].sudo().search_count([
                ('res_model', '=', 'purchase.order'),
                ('res_id', '=', order_id),
            ])
            if existing_count + len(attachments) > MAX_FILES:
                return {"success": False, "error": _("Maximum %s files allowed per dispute.") % MAX_FILES}

            for attachment_data in attachments:
                mimetype = attachment_data.get('mimetype', 'application/octet-stream')
                data = attachment_data.get('data', '')
                if mimetype not in ALLOWED_MIMETYPES:
                    return {"success": False, "error": _("File type not allowed.")}
                if data and (len(data) * 3 / 4) > MAX_SIZE:
                    return {"success": False, "error": _("File exceeds the 3 MB limit.")}
                request.env['ir.attachment'].sudo().create({
                    'name': attachment_data.get('name', 'attachment'),
                    'type': 'binary',
                    'datas': data,
                    'mimetype': mimetype,
                    'res_model': 'purchase.order',
                    'res_id': order_id,
                })

            order_attachment_ids = request.env['ir.attachment'].sudo().search_read(
                [('res_model', '=', 'purchase.order'), ('res_id', '=', order_id)],
                ['id', 'name', 'mimetype', 'file_size'],
                order='id asc',
            )
            return {"success": True, "attachments": order_attachment_ids}
        except Exception as e:
            _logger.error(f"Error uploading files to purchase order {order_id}: {str(e)}")
            return {"success": False, "error": str(e)}

    @http.route(
        ["/my/purchase/<int:order_id>/delete_file"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def delete_purchase_order_file(self, order_id, attachment_id=None, **kw):
        try:
            order_sudo = self._document_check_access('purchase.order', order_id)
        except (AccessError, MissingError):
            return {"success": False, "error": _("Purchase order not found")}

        try:
            attachment = request.env['ir.attachment'].sudo().search([
                ('id', '=', attachment_id),
                ('res_model', '=', 'purchase.order'),
                ('res_id', '=', order_sudo.id),
            ], limit=1)
            if not attachment:
                return {"success": False, "error": _("Document not found")}

            attachment.unlink()

            order_attachment_ids = request.env['ir.attachment'].sudo().search_read(
                [('res_model', '=', 'purchase.order'), ('res_id', '=', order_sudo.id)],
                ['id', 'name', 'mimetype', 'file_size'],
                order='id asc',
            )
            return {"success": True, "attachments": order_attachment_ids}
        except Exception as e:
            _logger.error(f"Error deleting file from purchase order {order_id}: {str(e)}")
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
        ref_sap = (filters.get('refSap') or '').strip()
        event = (filters.get('event') or '').strip()
        date_from = (filters.get('dateFrom') or '').strip()
        date_to = (filters.get('dateTo') or '').strip()

        if reference:
            domain.append(('name', 'ilike', reference))
        if ref_sap:
            domain.append(('x_ref_sap', 'ilike', ref_sap))
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
            'partner_id': {
                'fields': {
                    'id': {},
                    'name': {},
                    'street': {},
                    'street2': {},
                    'city': {},
                    'zip': {},
                    'state_id': {'fields': {'name': {}}},
                    'country_id': {'fields': {'name': {}}},
                    'vat': {},
                    'phone': {},
                }
            },
            'x_event_public_id': {'fields': {'id': {}, 'name': {}}},
            'x_event_id': {
                'fields': {
                    'id': {},
                    'name': {},
                    'service_id': {'fields': {'id': {}, 'name': {}}},
                }
            },
            'x_sub_service_id': {'fields': {'id': {}, 'name': {}}},
            'x_payment_event_type_id': {
                'fields': {
                    'id': {},
                    'name': {},
                }
            },
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
            'x_ref_sap': {},
            'x_authorized_amount': {},
            'x_dispute_authorized_amount': {},
        }

        result = request.env['purchase.order'].sudo().web_search_read(
            [('id', '=', order_id)], specification
        )

        if not result or not result.get('records'):
            return {}

        order_data = result['records'][0]

        # Supplier contact data (address/RFC/phone), read straight off partner_id
        supplier = order_data.get('partner_id')
        if supplier:
            supplier_address_parts = [
                supplier.get('street'),
                supplier.get('street2'),
                supplier.get('city'),
                supplier['state_id']['name'] if supplier.get('state_id') else False,
                supplier.get('zip'),
                supplier['country_id']['name'] if supplier.get('country_id') else False,
            ]
            order_data['x_supplier_address'] = ', '.join(part for part in supplier_address_parts if part)
            order_data['x_supplier_vat'] = supplier.get('vat') or ''
            order_data['x_supplier_phone'] = supplier.get('phone') or ''
        else:
            order_data['x_supplier_address'] = ''
            order_data['x_supplier_vat'] = ''
            order_data['x_supplier_phone'] = ''

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

        order_attachment_ids = request.env['ir.attachment'].sudo().search_read(
            [('res_model', '=', 'purchase.order'), ('res_id', '=', order_id)],
            ['id', 'name', 'mimetype', 'file_size'],
            order='id asc',
        )

        # ir.attachment.check() rejects portal users outright, so /web/image
        # and /web/content links only work with a matching per-attachment
        # access_token. Generate one for every attachment shown on this page.
        all_attachment_ids = [a['id'] for a in order_attachment_ids]
        for msg in messages:
            all_attachment_ids += [a['id'] for a in (msg.get('attachment_ids') or [])]

        if all_attachment_ids:
            attachments = request.env['ir.attachment'].sudo().browse(all_attachment_ids)
            token_by_id = dict(zip(attachments.ids, attachments.generate_access_token()))

            for att in order_attachment_ids:
                att['access_token'] = token_by_id.get(att['id'])
            for msg in messages:
                for att in (msg.get('attachment_ids') or []):
                    att['access_token'] = token_by_id.get(att['id'])

        order_data['order_attachment_ids'] = order_attachment_ids

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

        # Invoicing company data, sourced directly from purchase.order.x_invoice_company_id.
        # Older orders never got this field populated at creation time, so fall back to
        # deriving it from the linked event's account (same lookup the portal used before).
        invoice_companies = order.x_invoice_company_id
        if not invoice_companies:
            if order.x_event_id:
                fallback_events = order.x_event_id
            else:
                names_events = order.order_line.mapped('x_parent_expedient')
                fallback_events = request.env['ike.event'].sudo().search([('name', 'in', names_events)])
            invoice_companies = fallback_events.account_id.x_invoice_company_id
        _logger.info(f"Invoice company for order {order_id}: {invoice_companies}")

        if invoice_companies:
            order_data['x_invoice_company_names'] = ', '.join(invoice_companies.mapped('name'))
            addresses = []
            for company in invoice_companies:
                address_parts = [
                    company.street,
                    company.street2,
                    company.city,
                    company.state_id.name if company.state_id else False,
                    company.zip,
                    company.country_id.name if company.country_id else False,
                ]
                address = ', '.join(part for part in address_parts if part)
                if address:
                    addresses.append(address)
            order_data['x_invoice_company_address'] = ', '.join(addresses)
            order_data['x_invoice_company_phone'] = ', '.join(filter(None, invoice_companies.mapped('phone')))
            order_data['x_invoice_company_vat'] = ', '.join(filter(None, invoice_companies.mapped('vat')))
        else:
            order_data['x_invoice_company_names'] = ''
            order_data['x_invoice_company_address'] = ''
            order_data['x_invoice_company_phone'] = ''
            order_data['x_invoice_company_vat'] = ''

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

                # Invoicing company, sourced directly from purchase.order.x_invoice_company_id.
                # Older orders never got this field populated at creation time, so fall back to
                # deriving it from the linked event's account (same lookup the portal used before).
                invoice_companies = order.x_invoice_company_id
                if not invoice_companies:
                    if event:
                        fallback_events = event
                    else:
                        names_events = order.order_line.mapped('x_parent_expedient')
                        fallback_events = request.env['ike.event'].sudo().search([('name', 'in', names_events)])
                    invoice_companies = fallback_events.account_id.x_invoice_company_id
                x_invoice_company_names = ', '.join(invoice_companies.mapped('name')) if invoice_companies else ''

                # 4. Extract full multi-layered invoice metadata safely with sudo override,
                # scoped to the order's invoicing company
                invoices_data = []
                if order.invoice_ids:
                    invoice_domain = [('id', 'in', order.invoice_ids.ids)]
                    # if invoice_companies:
                    #     invoice_domain.append(('commercial_partner_id', 'in', invoice_companies.ids))
                    invoices_data = request.env['account.move'].sudo().search_read(
                        domain=invoice_domain,
                        fields=['id', 'name', 'state', 'payment_state', 'amount_total']
                    )

                records.append({
                    'id': order.id,
                    'name': order.name,
                    'state': order.state,
                    'invoice_status': order.invoice_status,
                    'x_dispute_state': order.x_dispute_state,
                    'x_dispute_approved': order.x_dispute_approved,
                    'x_event_id': event_data,
                    'date_approve': str(order.date_approve) if order.date_approve else False,
                    'date_planned': str(order.date_planned) if order.date_planned else False,
                    'amount_total': order.amount_untaxed,
                    'invoice_ids': invoices_data,
                    'x_origin_events': order.x_origin_events or '',
                    'x_ref_sap': order.x_ref_sap or '',
                    'partner_id': {'id': order.partner_id.id, 'name': order.partner_id.name} if order.partner_id else False,
                    'x_invoice_company_names': x_invoice_company_names,
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
            domain = expression.AND([
                self._get_purchase_order_portal_domain(kw),
                [('state', 'in', ['purchase', 'done'])],
            ])
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

    @http.route('/my/purchase/download_orders_xlsx', type='http', auth='user', website=True)
    def download_orders_xlsx(self, **kw):
        """Export the portal statement with the same scope as the PDF."""
        try:
            domain = expression.AND([
                self._get_purchase_order_portal_domain(kw),
                [('state', 'in', ['purchase', 'done'])],
            ])
            orders = request.env['purchase.order'].sudo().search(
                domain, order='date_approve desc, id desc'
            )
            if not orders:
                return request.redirect('/my/purchase')

            report_model = request.env[
                'report.ike_event_purchase.report_portal_purchase_orders'
            ].sudo()
            values = report_model._get_report_values(
                orders.ids, data={'filters': kw}
            )

            output = io.BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Estado de cuenta')
            worksheet.hide_gridlines(2)

            title_format = workbook.add_format({
                'bold': True, 'font_size': 18, 'font_color': '#15006A',
            })
            subtitle_format = workbook.add_format({
                'font_size': 10, 'font_color': '#4B4F75',
            })
            label_format = workbook.add_format({
                'bold': True, 'font_color': '#2437C7', 'bg_color': '#EEF1FF',
                'border': 1, 'border_color': '#CFD5F5',
            })
            value_format = workbook.add_format({
                'bold': True, 'bg_color': '#EEF1FF', 'border': 1,
                'border_color': '#CFD5F5',
            })
            money_summary_format = workbook.add_format({
                'bold': True, 'bg_color': '#EEF1FF', 'border': 1,
                'border_color': '#CFD5F5', 'num_format': '#,##0.00',
            })
            header_format = workbook.add_format({
                'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#16006F',
                'border': 1, 'border_color': '#16006F', 'align': 'center',
                'valign': 'vcenter',
            })
            text_format = workbook.add_format({
                'border': 1, 'border_color': '#DFE3F1', 'valign': 'top',
            })
            date_format = workbook.add_format({
                'border': 1, 'border_color': '#DFE3F1',
                'num_format': 'dd/mm/yyyy', 'valign': 'top',
            })
            money_format = workbook.add_format({
                'border': 1, 'border_color': '#DFE3F1',
                'num_format': '#,##0.00', 'valign': 'top',
            })

            worksheet.merge_range('A1:G1', 'Estado de cuenta', title_format)
            worksheet.merge_range(
                'A2:G2',
                '%s órdenes incluidas' % len(orders),
                subtitle_format,
            )
            worksheet.write('A3', 'Proveedor', label_format)
            worksheet.merge_range(
                'B3:G3', values['supplier_info']['name'], value_format
            )

            row = 3
            if values['applied_filters']:
                filters_text = ' | '.join(
                    '%s: %s' % item for item in values['applied_filters']
                )
                worksheet.write(row, 0, 'Filtros aplicados', label_format)
                worksheet.merge_range(row, 1, row, 6, filters_text, value_format)
                row += 1

            metrics = [
                ('Órdenes', len(orders), False),
                ('Pedidos sin facturar', values['uninvoiced_order_count'], False),
                ('Monto pendiente de facturar', values['pending_invoice_amount'], True),
                ('Facturas', values['invoice_count'], False),
                ('Subtotal facturado', values['invoiced_amount'], True),
                ('Subtotal pagado', values['paid_amount'], True),
                ('Pendiente a pagar', values['pending_payment_amount'], True),
                ('Facturas rechazadas', values['rejected_invoice_count'], False),
                ('Saldo cuenta', values['paid_amount'], True),
            ]
            for index, (label, value, is_money) in enumerate(metrics):
                metric_row = row + (index // 3)
                metric_col = (index % 3) * 2
                worksheet.write(metric_row, metric_col, label, label_format)
                worksheet.write(
                    metric_row,
                    metric_col + 1,
                    value,
                    money_summary_format if is_money else value_format,
                )

            table_row = row + 4
            headers = [
                'Orden', 'Evento', 'Fecha', 'Subtotal', 'Impuestos', 'Total',
                'Estado de facturación',
            ]
            for column, header in enumerate(headers):
                worksheet.write(table_row, column, header, header_format)

            for offset, order in enumerate(orders, start=1):
                current_row = table_row + offset
                order_label = order.name or ''
                if order.x_ref_sap:
                    order_label += '\nSAP %s' % order.x_ref_sap
                worksheet.write(current_row, 0, order_label, text_format)
                worksheet.write(
                    current_row, 1, report_model._order_event(order), text_format
                )
                order_date = order.date_approve or order.date_order
                if order_date:
                    worksheet.write_datetime(current_row, 2, order_date, date_format)
                else:
                    worksheet.write(current_row, 2, '-', text_format)
                worksheet.write_number(current_row, 3, order.amount_untaxed, money_format)
                worksheet.write_number(current_row, 4, order.amount_tax, money_format)
                worksheet.write_number(current_row, 5, order.amount_total, money_format)
                worksheet.write(
                    current_row,
                    6,
                    report_model._invoice_status(order),
                    text_format,
                )

            worksheet.autofilter(table_row, 0, table_row + len(orders), 6)
            worksheet.set_column('A:A', 22)
            worksheet.set_column('B:B', 22)
            worksheet.set_column('C:C', 14)
            worksheet.set_column('D:F', 18)
            worksheet.set_column('G:G', 24)
            workbook.close()
            xlsx_content = output.getvalue()
            headers = [
                (
                    'Content-Type',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ),
                ('Content-Length', len(xlsx_content)),
                (
                    'Content-Disposition',
                    content_disposition('ordenes_de_compra.xlsx'),
                ),
            ]
            return request.make_response(xlsx_content, headers=headers)
        except Exception as e:
            _logger.exception(
                "[Portal PO Controller] Error generating purchase orders XLSX: %s",
                str(e),
            )
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
            order.with_context(x_skip_dispute_amount_check=True).write({
                'x_dispute_iteration_count': dispute_count,
                'x_change_comments': change_comments,
                'order_line': order_lines,
            })
            return {'success': True}
        except Exception as e:
            _logger.error(f"Error saving purchase order dispute via RPC: {str(e)}")
            return {'success': False, 'error': str(e)}


class PortalInvoicePage(CustomerPortal):

    @http.route(
        ['/my/provider/invoices'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_my_invoices_custom(self, **kw):

        if not request.env.user.has_group(
            'ike_event_portal.custom_group_portal_finance'
        ):
            return request.redirect('/my')

        values = {
            'page_name': 'my_invoices_custom',
        }

        return request.render(
            'ike_event_purchase.portal_my_invoices_page',
            values
        )


class InvoicePortalController(http.Controller):

    def _get_invoice_domain(self, filters=None):

        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', '!=', 'cancel')
        ]

        supplier_id = self._get_supplier_id()

        if supplier_id:
            domain.append(
                ('partner_id', '=', supplier_id)
            )
        elif not request.env.user.has_group('base.group_system'):
            domain.append(('id', '=', 0))

        filters = filters or {}

        reference = (filters.get('reference') or '').strip()
        supplier = (filters.get('supplier') or '').strip()
        date_from = filters.get('dateFrom')
        date_to = filters.get('dateTo')
        status = (filters.get('status') or '').strip()

        if reference:
            domain.append(
                ('name', 'ilike', reference)
            )

        if supplier:
            domain.append(
                ('partner_id.name', 'ilike', supplier)
            )

        if date_from:
            domain.append(
                ('invoice_date', '>=', date_from)
            )

        if date_to:
            domain.append(
                ('invoice_date', '<=', date_to)
            )

        if status == 'cancel':
            domain.append(('state', '=', 'cancel'))
        elif status:
            domain.extend([
                ('state', '!=', 'cancel'),
                ('payment_state', '=', status),
            ])

        return domain

    def _get_supplier_id(self):
        relation = request.env['res.partner.supplier_users.rel'].sudo().search(
            [
                ('user_id', '=', request.env.user.id)
            ],
            limit=1
        )

        return relation.supplier_id.id if relation else False

    @http.route('/my/invoice/load_invoices', type='json', auth='user')
    def load_invoices(self):

        invoices = request.env['account.move'].sudo().search(
            self._get_invoice_domain()
        )

        records = []
        has_payment_receipt_field = (
            'x_payment_receipt_file'
            in request.env['account.move']._fields
        )

        for invoice in invoices:
            has_payment_receipt = bool(
                has_payment_receipt_field
                and invoice.payment_state == 'paid'
                and invoice.x_payment_receipt_file
            )

            records.append({
                'id': invoice.id,
                'name': invoice.name,
                'access_token': invoice.access_token or invoice._portal_ensure_token(),
                'invoice_date': (
                    str(invoice.invoice_date)
                    if invoice.invoice_date
                    else False
                ),
                'invoice_date_due': (
                    str(invoice.invoice_date_due)
                    if invoice.invoice_date_due
                    else False
                ),
                'amount_total': invoice.amount_total,
                'state': invoice.state,
                'payment_state': invoice.payment_state,
                'has_payment_receipt': has_payment_receipt,
                'payment_receipt_filename': (
                    invoice.x_payment_receipt_filename
                    if has_payment_receipt
                    else False
                ),
                'partner_id': {
                    'id': invoice.partner_id.id,
                    'name': invoice.partner_id.name
                },
            })

        return {
            'records': records
        }

    @http.route('/my/invoice/download_invoices_pdf', type='http', auth='user', website=True)
    def download_invoices_pdf(self, **kw):
        try:
            if not request.env.user.has_group(
                'ike_event_portal.custom_group_portal_finance'
            ):
                return request.redirect('/my')

            domain = self._get_invoice_domain(kw)

            invoices = request.env['account.move'].sudo().search(
                domain,
                order='invoice_date desc, id desc'
            )

            if not invoices:
                return request.make_response(
                    "No invoices found",
                    headers=[('Content-Type', 'text/plain')]
                )

            report = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'ike_event_purchase.action_report_portal_invoices',
                invoices.ids,
                data={
                    'report_type': 'pdf',
                    'filters': kw,
                }
            )[0]

            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(report)),
                (
                    'Content-Disposition',
                    content_disposition('facturas.pdf')
                ),
            ]

            return request.make_response(report, headers=headers)

        except Exception:
            raise
