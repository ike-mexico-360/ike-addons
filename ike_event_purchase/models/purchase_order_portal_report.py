# -*- coding: utf-8 -*-

import unicodedata

from odoo import api, fields, models
from odoo.tools import format_date


class PortalPurchaseOrdersReport(models.AbstractModel):
    _name = 'report.ike_event_purchase.report_portal_purchase_orders'
    _description = 'Portal Purchase Orders Statement Report'

    def _clean_text(self, value):
        if not value:
            return ''
        value = str(value)
        return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')

    def _format_money(self, amount, currency=None):
        symbol = self._clean_text(currency.symbol if currency else '$') or '$'
        return '%s %s' % (symbol, format(amount or 0.0, ',.2f'))

    def _format_date(self, value):
        if not value:
            return '-'
        return format_date(self.env, value)

    def _order_event(self, order):
        return self._clean_text(order.x_event_id.name or order.x_origin_events or '-')

    def _invoice_status(self, order):
        return {
            'invoiced': 'Totalmente facturado',
            'to invoice': 'Parcialmente facturado',
            'no': 'Factura en espera',
        }.get(order.invoice_status, order.invoice_status or '-')

    def _format_filter_date(self, value):
        if not value:
            return ''
        try:
            return format_date(self.env, fields.Date.to_date(value))
        except Exception:
            return self._clean_text(value)

    def _get_applied_filters(self, filters):
        filters = filters or {}
        applied = []
        reference = (filters.get('reference') or '').strip()
        ref_sap = (filters.get('refSap') or '').strip()
        event = (filters.get('event') or '').strip()
        date_from = (filters.get('dateFrom') or '').strip()
        date_to = (filters.get('dateTo') or '').strip()
        status = (filters.get('status') or '').strip()
        status_labels = {
            'state_purchase': 'Orden de compra',
            'state_done': 'Bloqueado',
            'state_cancel': 'Cancelado',
            'inv_waiting': 'Factura en espera',
            'inv_partial': 'Parcialmente facturado',
            'inv_full': 'Totalmente facturado',
        }

        if reference:
            applied.append(('Referencia', self._clean_text(reference)))
        if ref_sap:
            applied.append(('Referencia SAP', self._clean_text(ref_sap)))
        if event:
            applied.append(('Evento', self._clean_text(event)))
        if date_from:
            applied.append(('Fecha desde', self._format_filter_date(date_from)))
        if date_to:
            applied.append(('Fecha hasta', self._format_filter_date(date_to)))
        if status:
            applied.append(('Estado', status_labels.get(status, status)))
        return applied

    def _get_supplier_info(self, orders):
        suppliers = orders.mapped('partner_id')
        if not suppliers:
            return {'name': '-', 'details': ''}
        if len(suppliers) > 1:
            return {
                'name': 'Varios proveedores',
                'details': '%s proveedores incluidos' % len(suppliers),
            }

        supplier = suppliers[0]
        details = []
        if supplier.vat:
            details.append('RFC %s' % self._clean_text(supplier.vat))
        if supplier.phone:
            details.append(self._clean_text(supplier.phone))
        if supplier.email:
            details.append(self._clean_text(supplier.email))
        return {
            'name': self._clean_text(supplier.name),
            'details': ' | '.join(details),
        }

    def _get_invoice_metrics(self, orders):
        invoices = orders.mapped('invoice_ids')
        active_invoices = invoices.filtered(lambda inv: inv.state != 'cancel')
        paid_invoices = active_invoices.filtered(lambda inv: inv.state == 'posted' and inv.payment_state == 'paid')
        pending_payment_invoices = active_invoices.filtered(
            lambda inv: inv.state == 'posted' and inv.payment_state in ('not_paid', 'partial')
        )
        invoiced_amount = sum(active_invoices.mapped('amount_total'))
        paid_amount = sum(paid_invoices.mapped('amount_total'))
        pending_payment_amount = sum(pending_payment_invoices.mapped('amount_total'))
        pending_invoice_amount = sum(orders.mapped('amount_total')) - invoiced_amount
        return {
            'invoice_count': len(active_invoices),
            'rejected_invoice_count': len(invoices.filtered(lambda inv: inv.state == 'cancel')),
            'invoiced_amount': invoiced_amount,
            'paid_amount': paid_amount,
            'pending_payment_amount': pending_payment_amount,
            'pending_invoice_amount': pending_invoice_amount if pending_invoice_amount > 0 else 0,
            'uninvoiced_order_count': len(orders.filtered(lambda order: not order.invoice_ids)),
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        orders = self.env['purchase.order'].browse(docids)
        company = orders[:1].company_id if orders else self.env.company
        data = data or {}
        invoice_metrics = self._get_invoice_metrics(orders)
        return {
            'doc_ids': docids,
            'doc_model': 'purchase.order',
            'docs': orders,
            'company': company,
            'supplier_info': self._get_supplier_info(orders),
            'applied_filters': self._get_applied_filters(data.get('filters')),
            'clean_text': self._clean_text,
            'format_money': self._format_money,
            'format_statement_date': self._format_date,
            'order_event': self._order_event,
            'invoice_status': self._invoice_status,
            'total_untaxed': sum(orders.mapped('amount_untaxed')),
            'total_tax': sum(orders.mapped('amount_tax')),
            'total_amount': sum(orders.mapped('amount_total')),
            **invoice_metrics,
        }


class PortalInvoicesReport(models.AbstractModel):
    _name = 'report.ike_event_purchase.report_portal_invoices'
    _description = 'Portal Invoices Statement Report'

    def _clean_text(self, value):
        if not value:
            return ''
        value = str(value)
        return unicodedata.normalize('NFKD', value).encode(
            'ascii', 'ignore'
        ).decode('ascii')

    def _format_money(self, amount, currency=None):
        symbol = self._clean_text(currency.symbol if currency else '$') or '$'
        return '%s %s' % (symbol, format(amount or 0.0, ',.2f'))

    def _format_date(self, value):
        if not value:
            return '-'
        return format_date(self.env, value)

    def _format_filter_date(self, value):
        if not value:
            return ''
        try:
            return format_date(self.env, fields.Date.to_date(value))
        except Exception:
            return self._clean_text(value)

    def _get_applied_filters(self, filters):
        filters = filters or {}
        applied = []
        reference = (filters.get('reference') or '').strip()
        supplier = (filters.get('supplier') or '').strip()
        date_from = (filters.get('dateFrom') or '').strip()
        date_to = (filters.get('dateTo') or '').strip()
        status = (filters.get('status') or '').strip()
        status_labels = {
            'paid': 'Pagada',
            'not_paid': 'Pendiente de pago',
            'partial': 'Pago parcial',
            'in_payment': 'En proceso de pago',
            'reversed': 'Revertida',
            'cancel': 'Cancelada',
        }

        if reference:
            applied.append(('Factura', self._clean_text(reference)))
        if supplier:
            applied.append(('Proveedor', self._clean_text(supplier)))
        if date_from:
            applied.append(('Fecha desde', self._format_filter_date(date_from)))
        if date_to:
            applied.append(('Fecha hasta', self._format_filter_date(date_to)))
        if status:
            applied.append(('Estado', status_labels.get(status, status)))
        return applied

    def _get_supplier_info(self, invoices):
        suppliers = invoices.mapped('partner_id')
        if not suppliers:
            return {'name': '-', 'details': ''}
        if len(suppliers) > 1:
            return {
                'name': 'Varios proveedores',
                'details': '%s proveedores incluidos' % len(suppliers),
            }
        supplier = suppliers[0]
        return {
            'name': self._clean_text(supplier.name),
            'details': self._clean_text(supplier.vat or ''),
        }

    @api.model
    def _get_report_values(self, docids, data=None):
        invoices = self.env['account.move'].browse(docids)
        company = invoices[:1].company_id if invoices else self.env.company
        data = data or {}
        paid_invoices = invoices.filtered(
            lambda invoice: invoice.state != 'cancel'
            and invoice.payment_state == 'paid'
        )
        pending_invoices = invoices.filtered(
            lambda invoice: invoice.state != 'cancel'
            and invoice.payment_state in ('not_paid', 'partial')
        )
        return {
            'doc_ids': docids,
            'doc_model': 'account.move',
            'docs': invoices,
            'company': company,
            'supplier_info': self._get_supplier_info(invoices),
            'applied_filters': self._get_applied_filters(data.get('filters')),
            'clean_text': self._clean_text,
            'format_money': self._format_money,
            'format_statement_date': self._format_date,
            'invoiced_amount': sum(invoices.mapped('amount_total')),
            'paid_invoice_count': len(paid_invoices),
            'paid_amount': sum(paid_invoices.mapped('amount_total')),
            'pending_payment_amount': sum(
                pending_invoices.mapped('amount_total')
            ),
        }
