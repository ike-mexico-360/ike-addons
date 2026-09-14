/** @odoo-module */

import { useBus, useService } from "@web/core/utils/hooks";

import { Component, onWillStart, useState } from "@odoo/owl";

export class IkeEventListButtons extends Component {
    static template = "ike_event.IkeEventListButtons";
    static props = {
        viewClassName: { type: String, optional: true },
    };

    setup() {
        super.setup();

        this.orm = useService("orm");
        this.state = useState({
            showIkeListButtons: false,
        });

        onWillStart(async () => {
            await this.loadEventData();
            this.loadUserGroups();
        });

        useBus(this.env.bus, "IKE_EVENT_SYSTRAY:EVENT_LIST_RELOAD", async (event) => {
            // console.log(event.detail.payload.data);
            await this.loadEventData();
            this.render();
        });
        useBus(this.env.bus, "IKE_EVENT_SYSTRAY:EVENT_LIST_PUSH", async (event) => {
            // console.log(event.detail.payload.data);
            await this.loadEventData();
            this.render();
        });
    }
    async loadEventData() {
        // console.log("loadEventData");
        this.eventData = await this.orm.call("ike.event", "retrieve_event_data");
    }

    async loadUserGroups() {
        const splittedClassName = this.props.viewClassName !== null ? this.props.viewClassName.split(' ') : [];
        if (splittedClassName.includes('ike-show-table-buttons')) {
            this.state.showIkeListButtons = true;
        }
    }

    setSearchContext(ev) {
        const filter_name = ev.currentTarget.getAttribute("filter_name");
        const filters = filter_name.split(",");
        const searchItems = this.env.searchModel.getSearchItems((item) =>
            filters.includes(item.name)
        );
        this.env.searchModel.query = [];
        for (const item of searchItems) {
            this.env.searchModel.toggleSearchItem(item.id);
        }
    }
}
