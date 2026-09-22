/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { usePagination } from "@ike_event_portal/components/pagination/pagination_service";
import { PaginationComponent } from "@ike_event_portal/components/pagination/pagination_component";

export class PurchaseOrderReviewList extends Component {
    static template = "ike_event_purchase.PurchaseOrderReviewList";
    static components = { PaginationComponent };

    translate(str) { return _t(str); }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            orderReviews: [],
            showKpi: false,
            hasAdvancedPortal: false,
            filters: {
                reference: '',
                event: '',
            },
        });

        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredOrderReviews,
        });

        onWillStart(async () => {
            await Promise.all([this._loadOrderReviews(), this._loadCompanySettings(), this._checkAdvancedPortalPermission()]);
        });
    }

    // Checks if the logged-in user is a System Administrator or has the x_advanced_portal
    // flag set to True on their associated supplier contact record.
    async _checkAdvancedPortalPermission() {
        try {
            const res = await rpc('/my/purchase/get_advanced_portal_permission', {});

            if (res && res.error) {
                console.warn("[Order Review Permission Check] Warning:", res.error);
            }

            this.state.hasAdvancedPortal = res?.has_advanced_portal ?? false;
        } catch (e) {
            console.error("[Order Review Permission Check] RPC Error:", e);
            this.state.hasAdvancedPortal = false;
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

    get filteredOrderReviews() {
        const { reference, event } = this.state.filters;
        return this.state.orderReviews.filter(order => {
            if (reference && !(order.name || '').toLowerCase().includes(reference.toLowerCase())) return false;
            if (event) {
                const name = order.x_event_id ? order.x_event_id.name : '';
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

    async _loadOrderReviews() {
        this.state.loading = true;
        try {
            const res = await this.orm.webSearchRead('purchase.order', [
                ['state', 'in', ['to_consolidate', 'consolidated']],
            ], {
                specification: {
                    id: {},
                    name: {},
                    state: {},
                    x_event_id: { fields: { id: {}, name: {} } },
                    date_order: {},
                    amount_untaxed: {},
                },
            });
            this.state.orderReviews = res.records || [];
        } catch (e) {
            this.notification.add(_t("Error loading Order Reviews: ") + (e?.data?.message || e.message), {
                type: "danger", sticky: true,
            });
        } finally {
            this.state.loading = false;
        }
    }
    getStateLabel(state) {
        const states = {
            sent: _t("Sent"),
            to_consolidate: _t("To Consolidate"),
            consolidated: _t("Consolidated"),
        };

        return states[state] || state;
    }

    // 1. Total order reviews (Number of purchase orders under review)
    get totalOrderReviewsCount() {
        return this.filteredOrderReviews.length;
    }

    // 2. Subtotal (Sum of amount_untaxed of all order reviews)
    get subtotalOrderReviewsAmount() {
        return this.filteredOrderReviews.reduce((sum, order) => sum + (order.amount_untaxed || 0), 0);
    }

    // 3. Pending consolidation (orders still in 'to_consolidate')
    get toConsolidateCount() {
        return this.filteredOrderReviews.filter(order => order.state === 'to_consolidate').length;
    }

    // 4. Consolidated orders
    get consolidatedCount() {
        return this.filteredOrderReviews.filter(order => order.state === 'consolidated').length;
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

registry.category("public_components").add("ike_event_purchase.PurchaseOrderReviewList", PurchaseOrderReviewList);