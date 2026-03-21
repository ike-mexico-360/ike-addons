/** @odoo-module **/

import { Component } from "@odoo/owl";

export class PaginationComponent extends Component {
    static template = "ike_event_portal.PaginationComponent";

    static props = {
        pagination: { type: Object },
        showPageSize: { type: Boolean, optional: true },
        showInfo: { type: Boolean, optional: true },
        pageSizeOptions: { type: Array, optional: true },
        slots: { type: Object, optional: true },
    };

    static defaultProps = {
        showPageSize: true,
        showInfo: true,
        pageSizeOptions: [5, 10, 25, 50, 100],
    };

    onPageSizeChange(ev) {
        this.props.pagination.setPageSize(ev.target.value);
    }

    onPageClick(page) {
        this.props.pagination.goToPage(page);
    }

    onFirstPage() {
        this.props.pagination.firstPage();
    }

    onPrevPage() {
        this.props.pagination.prevPage();
    }

    onNextPage() {
        this.props.pagination.nextPage();
    }

    onLastPage() {
        this.props.pagination.lastPage();
    }
}