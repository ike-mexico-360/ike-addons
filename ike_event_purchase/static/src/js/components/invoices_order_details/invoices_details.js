/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime, deserializeDate, formatDate as formatDateOdoo } from "@web/core/l10n/dates";

export class InvoiceDetails extends Component {
    static template = "ike_event_purchase.InvoiceDetails";

    static props = {
        invoice_id: { type: Number, optional: false },
    };

    translate(str) { return _t(str); }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            invoice_data: null,
        });

        onWillStart(async () => {
            await this._loadInvoiceData();
        });
    }

    async _loadInvoiceData() {
        this.state.loading = true;
        try {
            const invoiceData = await rpc('/get_invoice_full_data', {
                invoice_id: this.props.invoice_id,
            });

            if (invoiceData) {
                this.state.invoice_data = invoiceData;
                console.log("Full Invoice Data:", this.state.invoice_data);
            }
        } catch (e) {
            this.notification.add(_t("Error loading invoice data: ") + (e?.data?.message || e.message), {
                type: "danger",
                sticky: true,
            });
        } finally {
            this.state.loading = false;
        }
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        try {
            const date = deserializeDate(dateStr);
            return formatDateOdoo(date);
        } catch {
            return dateStr;
        }
    }

    formatDateTime(dateStr) {
        if (!dateStr) return '';
        try {
            const date = deserializeDateTime(dateStr);
            return formatDateTime(date);
        } catch {
            return dateStr;
        }
    }

    formatCurrency(value) {
        if (value === undefined || value === null || value === '') return '';
        const num = parseFloat(value);
        if (isNaN(num)) return value;

        const l10n = this.env.services.localization || {
            decimalPoint: ".",
            thousandsSep: ",",
            grouping: [3],
        };

        const sessionInfo = window.odoo?.session_info;
        const symbol = sessionInfo?.currency_symbol || "$";
        const position = sessionInfo?.currency_position || "before";

        const parts = num.toFixed(2).split(".");
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, l10n.thousandsSep);
        const formattedNumber = parts.join(l10n.decimalPoint);

        return position === "before" ? `${symbol}${formattedNumber}` : `${formattedNumber} ${symbol}`;
    }

    get invoiceStatus() {
        const inv = this.state.invoice_data;
        if (!inv) return { label: '', cssClass: '' };
        if (inv.payment_state === 'paid') {
            return { label: _t('Paid'), cssClass: 'bg-success text-white' };
        }
        if (inv.payment_state === 'not_paid') {
            return { label: _t('Pending to Pay'), cssClass: 'bg-info text-white' };
        }
        if (inv.payment_state === 'partial') {
            return { label: _t('Partially Paid'), cssClass: 'bg-warning text-dark' };
        }
        return { label: _t('Draft'), cssClass: 'bg-secondary text-white' };
    }

    downloadPdf = () => {
        const params = new URLSearchParams();
        params.append('report_type', 'pdf');
        params.append('download', 'true');
        if (this.state.invoice_data?.access_token) {
            params.append('access_token', this.state.invoice_data.access_token);
        }
        window.open(`/my/invoices/${this.props.invoice_id}?${params.toString()}`, '_blank');
    }
}

registry.category("public_components").add("ike_event_purchase.InvoiceDetails", InvoiceDetails);