import base64
import io
import mimetypes

import xlsxwriter
from odoo import http
from odoo.addons.account.controllers.portal import PortalAccount
from odoo.exceptions import AccessError, MissingError
from odoo.http import content_disposition, request


class PortalInvoice(PortalAccount):

    @http.route(['/my/invoices/<int:invoice_id>'], type='http', auth='public', website=True)
    def portal_my_invoice_detail(self, invoice_id, access_token=None, report_type=None, download=False, **kw):
        try:
            invoice_sudo = self._document_check_access('account.move', invoice_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my/provider/invoices')

        if report_type in ('html', 'pdf', 'text'):
            has_generated_invoice = bool(invoice_sudo.invoice_pdf_report_id)
            request.update_context(proforma_invoice=not has_generated_invoice)

            report_action = request.env.ref('ike_event_portal_invoice.action_report_invoice_custom', raise_if_not_found=False)
            report_ref = report_action.report_name if report_action else invoice_sudo.x_get_name_invoice_report()
            return self._show_report(model=invoice_sudo, report_type=report_type, report_ref=report_ref, download=download)

        values = self._invoice_get_page_view_values(invoice_sudo, access_token, **kw)
        return request.render('account.portal_invoice_page', values)

    def _get_portal_invoice_export_domain(self, filters=None):
        """Build the same invoice scope used by the custom portal screen."""
        filters = filters or {}
        domain = [('move_type', '=', 'in_invoice')]

        supplier_relation = request.env[
            'res.partner.supplier_users.rel'
        ].sudo().search(
            [('user_id', '=', request.env.user.id)],
            limit=1,
        )
        is_admin = request.env.user.has_group('base.group_system')
        if not supplier_relation and not is_admin:
            return domain + [('id', '=', 0)]
        if supplier_relation:
            domain.append(
                ('partner_id', '=', supplier_relation.supplier_id.id)  # type: ignore
            )

        reference = (filters.get('reference') or '').strip()
        supplier = (filters.get('supplier') or '').strip()
        date_from = (filters.get('dateFrom') or '').strip()
        date_to = (filters.get('dateTo') or '').strip()
        status = (filters.get('status') or '').strip()

        if reference:
            domain.append(('name', 'ilike', reference))
        if supplier:
            domain.append(('partner_id.name', 'ilike', supplier))
        if date_from:
            domain.append(('invoice_date', '>=', date_from))
        if date_to:
            domain.append(('invoice_date', '<=', date_to))
        if status == 'cancel':
            domain.append(('state', '=', 'cancel'))
        elif status:
            domain.extend([
                ('state', '!=', 'cancel'),
                ('payment_state', '=', status),
            ])

        return domain

    @http.route(
        '/get_invoice_full_data',
        type='json',
        auth='public',
        website=True
    )
    def get_invoice_full_data(self, invoice_id, **kwargs):

        try:
            invoice = request.env['account.move'].sudo().browse(int(invoice_id))

            if not invoice.exists():
                return False

            # Validar que sea una factura
            if invoice.move_type not in (
                'out_invoice',
                'out_refund',
                'in_invoice',
                'in_refund',
            ):
                return False

            partner = invoice.partner_id
            company = invoice.company_id

            return {
                'id': invoice.id,
                'name': invoice.name,

                # Partner / proveedor
                'partner_id': {
                    'id': partner.id,
                    'name': partner.name,
                } if partner else False,

                'x_supplier_address': partner.contact_address if partner else False,
                'x_supplier_vat': partner.vat if partner else False,
                'x_supplier_phone': partner.phone if partner else False,

                # Empresa facturadora
                'company_id': {
                    'id': company.id,
                    'name': company.name,
                } if company else False,

                'x_company_address': company.partner_id.contact_address if company else False,
                'x_company_vat': company.vat if company else False,
                'x_company_phone': company.phone if company else False,

                # Fechas
                'invoice_date': invoice.invoice_date,
                'invoice_date_due': invoice.invoice_date_due,

                # Referencias
                'ref': invoice.ref,
                'invoice_origin': invoice.invoice_origin,

                # Estado
                'state': invoice.state,
                'payment_state': invoice.payment_state,

                # Portal
                'access_token': invoice.access_token,
            }

        except Exception as e:
            return {
                'error': str(e)
            }

    @http.route(
        ['/provider/portal/invoice/dian'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_invoice_dian(self, **kw):
        if not request.env.user.has_group('ike_event_portal.custom_group_portal_finance'):
            return request.redirect('/my')

        return request.redirect('/my/provider/invoices')

    @http.route(
        ['/my/invoices/<int:invoice_id>/payment_receipt'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_invoice_payment_receipt(self, invoice_id, **kw):
        """Download a paid invoice receipt within the user's portal scope."""
        if not request.env.user.has_group(
            'ike_event_portal.custom_group_portal_finance'
        ):
            return request.redirect('/my')

        domain = self._get_portal_invoice_export_domain()
        domain.extend([
            ('id', '=', invoice_id),
            ('state', '!=', 'cancel'),
            ('payment_state', '=', 'paid'),
        ])
        invoice = request.env['account.move'].sudo().search(
            domain,
            limit=1,
        )
        if not invoice or not invoice.x_payment_receipt_file:
            return request.not_found()

        filename = (
            invoice.x_payment_receipt_filename
            or 'comprobante_pago.pdf'
        )
        content = base64.b64decode(invoice.x_payment_receipt_file)
        mimetype = (
            mimetypes.guess_type(filename)[0]
            or 'application/octet-stream'
        )
        return request.make_response(
            content,
            headers=[
                ('Content-Type', mimetype),
                ('Content-Length', len(content)),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )

    @http.route(
        ['/my/invoices/download/xlsx'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_invoices_xlsx(
        self,
        reference='',
        supplier='',
        dateFrom='',
        dateTo='',
        status='',
        **kw,
    ):
        """Export the portal invoice list using the active filters and sorting."""
        if not request.env.user.has_group(
            'ike_event_portal.custom_group_portal_finance'
        ):
            return request.redirect('/my')

        filters = {
            'reference': reference,
            'supplier': supplier,
            'dateFrom': dateFrom,
            'dateTo': dateTo,
            'status': status,
        }
        invoices = request.env['account.move'].sudo().search(
            self._get_portal_invoice_export_domain(filters),
            order='invoice_date desc, id desc',
        )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Estado de facturas')
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
        amount_format = workbook.add_format({
            'border': 1, 'border_color': '#DFE3F1',
            'num_format': '#,##0.00', 'valign': 'top',
        })

        worksheet.merge_range('A1:E1', 'Estado de facturas', title_format)  # type: ignore
        worksheet.merge_range(
            'A2:E2',
            '%s facturas incluidas' % len(invoices),  # type: ignore
            subtitle_format,
        )
        worksheet.write('A3', 'Proveedor', label_format)
        suppliers = invoices.mapped('partner_id')
        if len(suppliers) == 1:
            supplier_name = suppliers.name
        elif len(suppliers) > 1:
            supplier_name = 'Varios proveedores'
        else:
            supplier_name = '-'
        worksheet.merge_range(
            'B3:E3', supplier_name, value_format  # type: ignore
        )

        total_invoiced = sum(invoices.mapped('amount_total'))
        pending_amount = sum(invoices.mapped('amount_residual'))
        paid_amount = total_invoiced - pending_amount
        worksheet.write('A4', 'Facturas', label_format)
        worksheet.write('B4', len(invoices), value_format)
        worksheet.write('C4', 'Total facturado', label_format)
        worksheet.merge_range('D4:E4', total_invoiced, money_summary_format)  # type: ignore
        worksheet.write('A5', 'Subtotal pagado', label_format)
        worksheet.write('B5', paid_amount, money_summary_format)
        worksheet.write('C5', 'Pendiente a pagar', label_format)
        worksheet.merge_range('D5:E5', pending_amount, money_summary_format)  # type: ignore

        status_labels = {
            'paid': 'Pagada',
            'not_paid': 'Pendiente de pago',
            'cancel': 'Cancelada',
        }
        applied_filters = []
        if reference:
            applied_filters.append('Factura: %s' % reference)
        if dateFrom:
            applied_filters.append('Fecha desde: %s' % dateFrom)
        if dateTo:
            applied_filters.append('Fecha hasta: %s' % dateTo)
        if status:
            applied_filters.append(
                'Estado: %s' % status_labels.get(status, status)
            )
        if applied_filters:
            worksheet.write('A6', 'Filtros aplicados', label_format)
            worksheet.merge_range(
                'B6:E6', ' | '.join(applied_filters), value_format
            )

        headers = [
            'Factura #',
            'Fecha de factura',
            'Fecha de vencimiento',
            'Cantidad por pagar',
            'Estado',
        ]
        table_row = 7 if applied_filters else 6
        for column, title in enumerate(headers):
            worksheet.write(table_row, column, title, header_format)

        worksheet.set_column('A:A', 24)
        worksheet.set_column('B:C', 20)
        worksheet.set_column('D:D', 22)
        worksheet.set_column('E:E', 24)

        for offset, invoice in enumerate(invoices, start=1):
            row = table_row + offset
            if invoice.state == 'cancel':
                status = 'Cancelada'
            elif invoice.currency_id.is_zero(invoice.amount_residual):
                status = 'Pagada'
            elif invoice.payment_state == 'in_payment':
                status = 'En proceso de pago'
            elif invoice.payment_state == 'reversed':
                status = 'Revertida'
            else:
                status = 'En espera del pago'

            worksheet.write(row, 0, invoice.name or '', text_format)
            if invoice.invoice_date:
                worksheet.write_datetime(
                    row, 1, invoice.invoice_date, date_format
                )
            else:
                worksheet.write(row, 1, '-', text_format)
            if invoice.invoice_date_due:
                worksheet.write_datetime(
                    row, 2, invoice.invoice_date_due, date_format
                )
            else:
                worksheet.write(row, 2, '-', text_format)
            amount_due = (
                -invoice.amount_residual
                if invoice.move_type == 'out_refund'
                else invoice.amount_residual
            )
            worksheet.write_number(row, 3, amount_due, amount_format)
            worksheet.write(row, 4, status, text_format)

        worksheet.autofilter(
            table_row, 0, table_row + len(invoices), len(headers) - 1
        )
        workbook.close()
        output.seek(0)
        xlsx_content = output.getvalue()

        return request.make_response(
            xlsx_content,
            headers=[
                (
                    'Content-Type',
                    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                ),
                ('Content-Length', len(xlsx_content)),
                (
                    'Content-Disposition',
                    content_disposition('facturas.xlsx'),
                ),
            ],
        )
