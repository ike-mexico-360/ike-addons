/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
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
            await this._loadRfqs();
        });
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

    async _loadRfqs() {
        this.state.loading = true;
        try {
            const res = await this.orm.webSearchRead('purchase.order', [['state', 'in', ['sent', 'to_consolidate', 'consolidated']], ['x_dispute_state', 'not in', ['open', 'submitted']]], {
                specification: {
                    id: {},
                    name: {},
                    state: {},
                    x_event_id: { fields: { id: {}, name: {} } },
                    date_order: {},
                    amount_untaxed: {},
                    amount_untaxed_dispute: {},
                    amount_untaxed_approved: {},
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
}

registry.category("public_components").add("ike_event_purchase.PurchaseRfqList", PurchaseRfqList);
