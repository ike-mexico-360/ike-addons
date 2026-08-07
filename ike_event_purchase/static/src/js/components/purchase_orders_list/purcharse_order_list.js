/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { usePagination } from "@ike_event_portal/components/pagination/pagination_service";
import { PaginationComponent } from "@ike_event_portal/components/pagination/pagination_component";

export class PurchaseOrderList extends Component {
    static template = "ike_event_purchase.PurchaseOrderList";

    static components = { PaginationComponent };

    translate(str) { return _t(str); }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            orders: [],
            showKpi: false,
            filters: {
                reference: '',
                refSap: '',
                event: '',
                dateFrom: '',
                dateTo: '',
                status: '',
            },
            satOrderId: null,
            satHistoryLines: [],
            satHistoryLoading: false,
        });

        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredOrders,
        });

        onWillStart(async () => {
            await Promise.all([this._loadOrders(), this._loadCompanySettings()]);
        });
    }

    get filteredOrders() {
        const { reference, refSap, event, dateFrom, dateTo, status } = this.state.filters;
        const from = dateFrom ? new Date(dateFrom) : null;
        const to = dateTo ? new Date(dateTo + 'T23:59:59') : null;
        return this.state.orders.filter(order => {
            if (reference && !(order.name || '').toLowerCase().includes(reference.toLowerCase())) return false;
            if (refSap && !(order.x_ref_sap || '').toLowerCase().includes(refSap.toLowerCase())) return false;
            if (event) {
                const term = event.toLowerCase();
                const eventName = (order.x_event_id ? order.x_event_id.name : '').toLowerCase();
                const originEvents = (order.x_origin_events || '').toLowerCase();
                if (!eventName.includes(term) && !originEvents.includes(term)) return false;
            }
            if (from || to) {
                const approveDate = order.date_approve ? new Date(order.date_approve) : null;
                if (!approveDate) return false;
                if (from && approveDate < from) return false;
                if (to && approveDate > to) return false;
            }
            if (status && !this._orderMatchesStatus(order, status)) return false;
            return true;
        });
    }

    async openSatHistoryModal(orderId) {
        this.state.satOrderId = orderId;
        this.state.satHistoryLines = [];
        this.state.satHistoryLoading = true;
        try {
            const res = await rpc('/my/purchase/get_sat_validator_history', { purchase_order_id: orderId });
            if (res && res.error) {
                throw new Error(res.error);
            }
            this.state.satHistoryLines = res.lines || [];
        } catch (e) {
            this.notification.add(_t("Error loading SAT validator history: ") + (e.message || e), {
                type: "danger",
            });
        } finally {
            this.state.satHistoryLoading = false;
        }
    }

    getSatStatusBadgeClass(satStatus) {
        if (satStatus === 'Vigente') return 'bg-success';
        if (['Cancelado', 'Error'].includes(satStatus)) return 'bg-danger';
        return 'bg-warning text-dark';
    }

    getSatLineStateBadgeClass(lineState) {
        if (lineState === 'validated') return 'bg-success';
        if (lineState === 'xml_error') return 'bg-danger';
        return 'bg-info';
    }

    _orderMatchesStatus(order, status) {
        switch (status) {
            // Estado (purchase.order.state): only the 3 states the portal ever shows
            case 'state_purchase':
                return order.state === 'purchase';
            case 'state_done':
                return order.state === 'done';
            case 'state_cancel':
                return order.state === 'cancel';
            // Facturación (invoice_status): Factura en espera / Parcialmente facturado / Totalmente facturado
            case 'inv_waiting':
            case 'inv_partial':
            case 'inv_full':
                return this.getInvoiceStatus(order).key === status;
            // De pago
            case 'pay_pending': // Por pagar
                return (order.invoice_ids || []).some(
                    inv => inv.state === 'posted' && ['not_paid', 'partial'].includes(inv.payment_state)
                );
            case 'pay_paid': { // Pagado
                const postedInvoices = (order.invoice_ids || []).filter(inv => inv.state === 'posted');
                if (!postedInvoices.length) return false;
                return postedInvoices.every(inv => inv.payment_state === 'paid');
            }
            default:
                return true;
        }
    }

    onFilterChange(filterName, value) {
        this.state.filters[filterName] = value;
        this.pagination.reset();
    }

    clearFilters() {
        this.state.filters.reference = '';
        this.state.filters.refSap = '';
        this.state.filters.event = '';
        this.state.filters.dateFrom = '';
        this.state.filters.dateTo = '';
        this.state.filters.status = '';
        this.pagination.reset();
    }

    downloadOrdersPdf() {
        if (!this.filteredOrders.length) {
            this.notification.add(_t("No purchase orders to download."), { type: "warning" });
            return;
        }

        const params = new URLSearchParams();
        for (const [key, value] of Object.entries(this.state.filters)) {
            if (value) {
                params.append(key, value);
            }
        }
        const queryString = params.toString();
        window.open(`/my/purchase/download_orders_pdf${queryString ? `?${queryString}` : ''}`, '_blank');
    }

    // Suma facturada de un pedido (facturas publicadas, sin cancelar)
    getInvoicedTotal(order) {
        return (order.invoice_ids || [])
            .filter(inv => inv.state === 'posted')
            .reduce((sum, inv) => sum + (inv.amount_total || 0), 0);
    }

    // Order's own OC-lifecycle status, reusing the same labels as the Estatus filter
    getOrderStatus(order) {
        switch (order.state) {
            case 'sent':
                return { label: _t('Cost Review'), cssClass: 'bg-warning text-dark' };
            case 'to_consolidate':
                return { label: _t('To Consolidate'), cssClass: 'bg-info text-dark' };
            case 'consolidated':
                return { label: _t('Consolidated'), cssClass: 'bg-primary' };
            case 'purchase':
                return { label: _t('Purchase Order'), cssClass: 'bg-success' };
            case 'done':
                return { label: _t('Locked'), cssClass: 'bg-secondary' };
            case 'cancel':
                return { label: _t('Cancelled'), cssClass: 'bg-danger' };
            default:
                return { label: order.state, cssClass: 'bg-light text-dark' };
        }
    }

    // Estado de facturación: leído directamente del campo purchase.order.invoice_status
    // ('no' / 'to invoice' / 'invoiced'), la misma fuente que usa el backend de Odoo.
    // Single source of truth shared by the "Estado Factura" column and the Status filter.
    getInvoiceStatus(order) {
        switch (order.invoice_status) {
            case 'invoiced':
                return { key: 'inv_full', label: _t('Totalmente facturado'), cssClass: 'badge-invoice-full' };
            case 'to invoice':
                return { key: 'inv_partial', label: _t('Parcialmente facturado'), cssClass: 'badge-invoice-partial' };
            default: // 'no'
                return { key: 'inv_waiting', label: _t('Factura en espera'), cssClass: 'badge-invoice-waiting' };
        }
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const date = deserializeDateTime(dateStr);
            return formatDateTime(date);
        } catch {
            return dateStr;
        }
    }

    async _loadCompanySettings() {
        try {
            const result = await this.orm.webSearchRead(
                'res.company',
                [],
                { specification: { x_display_po_summary_portal: {} }, limit: 1 }
            );
            this.state.showKpi = result.records[0]?.x_display_po_summary_portal ?? false;
        } catch {
            this.state.showKpi = false;
        }
    }

    async _loadOrders() {
        this.state.loading = true;
        try {
            console.log("[PO Loader] Initiating custom RPC controller fetch via /my/purchase/load_orders_analytics...");

            // Use standard Odoo 18 RPC service instead of direct ORM models searchRead
            const res = await rpc('/my/purchase/load_orders_analytics', {});

            if (res && res.error) {
                throw new Error(res.error);
            }

            console.log("[PO Loader] Sudo controller response received:", res);
            this.state.orders = res.records || [];

            // Debug previews
            if (this.state.orders.length > 0) {
                console.group("[PO Loader] First 3 Orders Invoice Preview (Sudo Stream)");
                this.state.orders.slice(0, 3).forEach(order => {
                    console.log(
                        `Order: ${order.name} | Invoices Count: ${order.invoice_ids?.length || 0}`,
                        order.invoice_ids
                    );
                });
                console.groupEnd();
            }

        } catch (e) {
            console.error("[PO Loader] Critical error during controller RPC fetch:", e);
            this.notification.add(_t("Error loading purchase orders data: ") + (e.message || e), {
                type: "danger", sticky: true,
            });
        } finally {
            this.state.loading = false;
            console.log("[PO Loader] Load execution finished. Loading state:", this.state.loading);
        }
    }

    // 1. Total ordenes (Number of purchase orders)
    get totalOrdersCount() {
        return this.filteredOrders.length;
    }

    // 2. Subtotal OC (Sum of amount_total of all POs)
    get subtotalOrdersAmount() {
        return this.filteredOrders.reduce((sum, order) => sum + (order.amount_total || 0), 0);
    }

    // 3. Pedidos sin facturar (POs with no associated invoices)
    get unvoicedOrdersCount() {
        return this.filteredOrders.filter(order => !order.invoice_ids || order.invoice_ids.length === 0).length;
    }

    // 4. Monto pendiente de facturar (Uninvoiced balance from all POs)
    get pendingToInvoiceAmount() {
        return this.filteredOrders.reduce((sum, order) => {
            const orderTotal = order.amount_total || 0;
            const invoicedTotal = (order.invoice_ids || [])
                .filter(inv => inv.state !== 'cancel')
                .reduce((invSum, inv) => invSum + (inv.amount_total || 0), 0);

            const remaining = orderTotal - invoicedTotal;
            return sum + (remaining > 0 ? remaining : 0);
        }, 0);
    }

    // 5. Facturas (Total number of active invoices)
    get totalInvoicesCount() {
        return this.filteredOrders.reduce((sum, order) => {
            const activeInvoices = (order.invoice_ids || []).filter(inv => inv.state !== 'cancel');
            return sum + activeInvoices.length;
        }, 0);
    }

    // 6. Subtotal Facturado / Gastos total del periodo (Sum of amount_total of active invoices)
    get subtotalInvoicedAmount() {
        return this.filteredOrders.reduce((sum, order) => {
            const invoiceSum = (order.invoice_ids || [])
                .filter(inv => inv.state !== 'cancel')
                .reduce((invSum, inv) => invSum + (inv.amount_total || 0), 0);
            return sum + invoiceSum;
        }, 0);
    }

    // 7. Gastos total del periodo (Alias for total period expenses matching subtotal invoiced)
    get totalExpensesPeriod() {
        return this.subtotalInvoicedAmount;
    }

    // 8. Gastos promedio por factura (Total period expenses divided by the total active invoices count)
    get averageExpensePerInvoice() {
        const totalInvoices = this.totalInvoicesCount;
        if (totalInvoices === 0) {
            return 0.0;
        }
        return this.totalExpensesPeriod / totalInvoices;
    }

    // 9. Sub Total Pagado / Saldo cuenta (Sum of fully paid invoice amounts)
    get subtotalPaidAmount() {
        return this.filteredOrders.reduce((sum, order) => {
            const paidSum = (order.invoice_ids || [])
                .filter(inv => inv.state === 'posted' && inv.payment_state === 'paid')
                .reduce((invSum, inv) => invSum + (inv.amount_total || 0), 0);
            return sum + paidSum;
        }, 0);
    }

    // 10. Facturas rechazadas (Number of cancelled invoices)
    get rejectedInvoicesCount() {
        return this.filteredOrders.reduce((sum, order) => {
            const cancelledInvoices = (order.invoice_ids || []).filter(inv => inv.state === 'cancel');
            return sum + cancelledInvoices.length;
        }, 0);
    }

    // 11. Pendiente a pagar (Sum of invoices that are posted but not paid, or partially paid)
    get pendingToPayAmount() {
        return this.filteredOrders.reduce((sum, order) => {
            const unpaidSum = (order.invoice_ids || [])
                .filter(inv => inv.state === 'posted' && ['not_paid', 'partial'].includes(inv.payment_state))
                .reduce((invSum, inv) => invSum + (inv.amount_total || 0), 0);
            return sum + unpaidSum;
        }, 0);
    }

    // 12. Facturas pagadas (Number of fully paid invoices)
    get paidInvoicesCount() {
        return this.filteredOrders.reduce((sum, order) => {
            const paidCount = (order.invoice_ids || []).filter(inv => inv.state === 'posted' && inv.payment_state === 'paid').length;
            return sum + paidCount;
        }, 0);
    }
    formatCurrency(value) {
        if (value === undefined || value === null) {
            return "";
        }

        // 1. Gather structural localization configuration parameters from current browser environmental scope
        const l10n = this.env.services.localization || {
            decimalPoint: ".",
            thousandsSep: ",",
            grouping: [3],
        };

        // 2. Fetch active currency symbol and position metadata from global portal context injection
        const sessionInfo = window.odoo?.session_info;
        const symbol = sessionInfo?.currency_symbol || "$";
        const position = sessionInfo?.currency_position || "before";

        // 3. Perform clean float formatting step based on system separators
        const parts = parseFloat(value).toFixed(2).split(".");
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, l10n.thousandsSep);
        const formattedNumber = parts.join(l10n.decimalPoint);

        // 4. Return structural string following the native layout configuration
        return position === "before" ? `${symbol}${formattedNumber}` : `${formattedNumber} ${symbol}`;
    }
}

registry.category("public_components").add("ike_event_purchase.PurchaseOrderList", PurchaseOrderList);
