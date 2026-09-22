/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { usePagination } from "@ike_event_portal/components/pagination/pagination_service";
import { PaginationComponent } from "@ike_event_portal/components/pagination/pagination_component";

export class PurchaseRfqList extends Component {
    static template = "ike_event_purchase.PurchaseRfqList";

    static components = { PaginationComponent };

    translate(str) { return _t(str); }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            rfqs: [],
            showKpi: false,
            hasAdvancedPortal: false,
            filters: {
                reference: '',
                event: '',
            },
        });

        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredRfqs,
        });

        onWillStart(async () => {
            await Promise.all([
                this._loadRfqs(),
                this._loadCompanySettings(),
                this._checkAdvancedPortalPermission()
            ]);
        });
    }

    /**
     * Checks if the logged-in user is a System Administrator or has the x_advanced_portal
     * flag set to True on their associated supplier contact record.
     */
    async _checkAdvancedPortalPermission() {
        try {
            const res = await rpc('/my/purchase/get_advanced_portal_permission', {});

            if (res && res.error) {
                console.warn("[Portal Permission Check] Warning:", res.error);
            }

            this.state.hasAdvancedPortal = res?.has_advanced_portal ?? false;
        } catch (e) {
            console.error("[Portal Permission Check] RPC Error:", e);
            this.state.hasAdvancedPortal = false;
        }
    }

    get filteredRfqs() {
        const { reference, event } = this.state.filters;
        return this.state.rfqs.filter(rfq => {
            if (reference && !(rfq.name || '').toLowerCase().includes(reference.toLowerCase())) return false;
            if (event) {
                const name = rfq.x_event_id ? rfq.x_event_id.name : '';
                if (!name.toLowerCase().includes(event.toLowerCase())) return false;
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
        this.state.filters.event = '';
        this.pagination.reset();
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

    async _loadRfqs() {
        this.state.loading = true;
        try {
            const res = await this.orm.webSearchRead('purchase.order', [['state', 'in', ['sent']], ['x_dispute_state', 'not in', ['open', 'submitted']]], {
                specification: {
                    id: {},
                    name: {},
                    state: {},
                    x_event_id: { fields: { id: {}, name: {} } },
                    date_order: {},
                    amount_untaxed: {},
                    amount_untaxed_dispute: {},
                    amount_untaxed_approved: {},
                    amount_total: {},
                },
            });
            this.state.rfqs = res.records || [];
        } catch (e) {
            this.notification.add(_t("Error loading RFQs: ") + (e?.data?.message || e.message), {
                type: "danger", sticky: true,
            });
        } finally {
            this.state.loading = false;
        }
    }

    // 1. Total ordenes (Number of purchase orders / RFQs)
    get totalOrdersCount() {
        return this.filteredRfqs.length;
    }

    // 2. Subtotal OC (Sum of amount_untaxed of all RFQs)
    get subtotalOrdersAmount() {
        return this.filteredRfqs.reduce((sum, rfq) => sum + (rfq.amount_untaxed || 0), 0);
    }

    formatCurrency(value) {
        if (value === undefined || value === null) {
            return "";
        }

        const l10n = this.env.services.localization || {
            decimalPoint: ".",
            thousandsSep: ",",
            grouping: [3],
        };

        const sessionInfo = window.odoo?.session_info;
        const symbol = sessionInfo?.currency_symbol || "$";
        const position = sessionInfo?.currency_position || "before";

        const parts = parseFloat(value).toFixed(2).split(".");
        parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, l10n.thousandsSep);
        const formattedNumber = parts.join(l10n.decimalPoint);

        return position === "before" ? `${symbol}${formattedNumber}` : `${formattedNumber} ${symbol}`;
    }
}

registry.category("public_components").add("ike_event_purchase.PurchaseRfqList", PurchaseRfqList);