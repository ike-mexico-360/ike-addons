/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { usePagination } from "@ike_event_portal/components/pagination/pagination_service";
import { PaginationComponent } from "@ike_event_portal/components/pagination/pagination_component";

export class InvoiceOrderList extends Component {
    static template = "ike_event_purchase.InvoiceList";

    static components = { PaginationComponent };

    translate(str) { return _t(str); }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            invoices: [],
            showKpi: false,
            filters:{
                reference:'',
                supplier:'',
                dateFrom:'',
                dateTo:'',
                status:'',
            }
        });

        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredInvoices,
        });

        onWillStart(async () => {
            await Promise.all([this._loadInvoices(), this._loadCompanySettings()]);
        });
    }

    get filteredInvoices() {
        const { reference, supplier, dateFrom, dateTo, status } = this.state.filters;
        const from = dateFrom ? new Date(dateFrom) : null;
        const to = dateTo ? new Date(dateTo + 'T23:59:59') : null;

        return this.state.invoices.filter(invoice => {
            // console.log({
            //     invoice: invoice.name,
            //     state: invoice.state,
            //     payment_state: invoice.payment_state,
            //     filter: status,
            // });

            if(reference &&
                !(invoice.name || '').toLowerCase()
                .includes(reference.toLowerCase())
            ){
                return false;
            }

            if(supplier){

                const supplierName =
                    invoice.partner_id?.name?.toLowerCase() || '';

                if(!supplierName.includes(supplier.toLowerCase())){
                    return false;
                }
            }

            if(from || to){

                const invoiceDate =
                    invoice.invoice_date ?
                    new Date(invoice.invoice_date) :
                    null;

                if(!invoiceDate)
                    return false;


                if(from && invoiceDate < from)
                    return false;


                if(to && invoiceDate > to)
                    return false;
            }
            if (status === 'cancel') {
                if (invoice.state !== 'cancel') {
                    return false;
                }
            } else if (status) {
                if (invoice.state === 'cancel') {
                    return false;
                }

                if (invoice.payment_state !== status) {
                    return false;
                }
            }

            return true;

        });
    }

    onFilterChange(filterName, value) {
        this.state.filters[filterName] = value;
        this.pagination.reset();
    }

    clearFilters() {
        this.state.filters.reference = '';
        this.state.filters.supplier = '';
        this.state.filters.dateFrom = '';
        this.state.filters.dateTo = '';
        this.state.filters.status = '';
        this.pagination.reset();
    }

    downloadInvoicesPdf() {
        if (!this.filteredInvoices.length) {
            this.notification.add(
                _t("No invoices to download."),
                { type: "warning" }
            );
            return;
        }

        const params = new URLSearchParams();

        for (const [key, value] of Object.entries(this.state.filters)) {
            if (value) {
                params.append(key, value);
            }
        }

        const queryString = params.toString();
        // console.log("Opening invoice PDF:", queryString);
        window.open(
            `/my/invoice/download_invoices_pdf${queryString ? `?${queryString}` : ''}`,
            '_blank'
        );
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

    async _loadInvoices() {
        this.state.loading = true;
        try {
            console.log("[PO Loader] Initiating custom RPC controller fetch via /my/purchase/load_orders_analytics...");

            // Use standard Odoo 18 RPC service instead of direct ORM models searchRead
            const res = await rpc('/my/invoice/load_invoices', {filters: this.state.filters});

            if (res && res.error) {
                throw new Error(res.error);
            }

            console.log("[Inovice Loader] Sudo controller response received:", res);
            this.state.invoices = res.records || [];

            // Debug previews
            if (this.state.invoices.length > 0) {
                console.group("[Inovice Loader] First 3 Orders Invoice Preview (Sudo Stream)");
                this.state.invoices.slice(0,3).forEach(invoice  => {
                    console.log(invoice);
                });
                console.groupEnd();
            }

        } catch (e) {
            console.error("[PO Loader] Critical error during controller RPC fetch:", e);
            this.notification.add(_t("Error loading invoices data: ") + (e.message || e), {
                type: "danger", sticky: true,
            });
        } finally {
            this.state.loading = false;
            console.log("[PO Loader] Load execution finished. Loading state:", this.state.loading);
        }
    }

    // 1. Total Invoice (Number of purchase orders)
    get totalInvoicesCount() {
        return this.filteredInvoices.length;
    }

    // 2. Subtotal OC (Sum of amount_total of all POs)
    get subtotalInvoicesAmount(){
        return this.filteredInvoices.reduce((sum, invoice)=> sum + (invoice.amount_total || 0), 0);
    }

    // 7. Gastos total del periodo (Alias for total period expenses matching subtotal invoiced)
    get totalExpensesPeriod() {
        return this.subtotalInvoicesAmount;
    }

    // 9. Sub Total Pagado / Saldo cuenta (Sum of fully paid invoice amounts)
    get subtotalPaidAmount() {
        return this.filteredInvoices
            .filter(inv => inv.payment_state === 'paid')
            .reduce((sum, inv) => sum + (inv.amount_total || 0), 0);
    }


    // 11. Pendiente a pagar (Sum of invoices that are posted but not paid, or partially paid)
    get pendingToPayAmount() {
        return this.filteredInvoices
            .filter(inv =>
                ['not_paid', 'partial'].includes(inv.payment_state)
            )
            .reduce(
                (sum, inv) => sum + (inv.amount_total || 0),
                0
            );
    }

    // 12. Facturas pagadas (Number of fully paid invoices)
    get paidInvoicesCount() {
        return this.filteredInvoices.filter(
            inv => inv.payment_state === 'paid'
        ).length;
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

    downloadInvoicesXlsx() {
        if (!this.filteredInvoices.length) {
            this.notification.add(
                _t("No invoices to download."),
                { type: "warning" }
            );
            return;
        }

        const params = new URLSearchParams();

        for (const [key, value] of Object.entries(this.state.filters)) {
            if (value) {
                params.append(key, value);
            }
        }

        const queryString = params.toString();

        window.open(
            `/my/invoices/download/xlsx${queryString ? `?${queryString}` : ''}`,
            '_blank'
        );
    }
    getInvoiceStatus(invoice) {
        if (invoice.payment_state === 'paid') {
            return {
                label: _t('Paid'),
                cssClass: 'bg-success text-white'
            };
        }
        if (invoice.payment_state === 'not_paid') {
            return {
                label: _t('Pending to Pay'),
                cssClass: 'bg-info text-white'
            };
        }

        return {
            label: _t('Draft'),
            cssClass: 'bg-secondary text-white'
        };
    }
}

registry.category("public_components").add("ike_event_purchase.InvoiceOrderList", InvoiceOrderList);
