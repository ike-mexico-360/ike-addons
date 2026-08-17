/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.ClientEventFilters = publicWidget.Widget.extend({
    selector: ".ike_client_event_filters",
    events: {
        "change select": "_onFilterChange",
        "change input[type='date']": "_onFilterChange",
        "input input[name='search']": "_onSearchInput",
    },

    init() {
        this._super(...arguments);
        this.searchTimer = null;
    },

    destroy() {
        clearTimeout(this.searchTimer);
        this._super(...arguments);
    },

    _onFilterChange() {
        clearTimeout(this.searchTimer);
        this.el.requestSubmit();
    },

    _onSearchInput() {
        clearTimeout(this.searchTimer);
        this.searchTimer = setTimeout(() => this.el.requestSubmit(), 450);
    },
});
