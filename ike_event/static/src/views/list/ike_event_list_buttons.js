/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

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
            this.eventData = await this.orm.call("ike.event", "retrieve_event_data");
            this.loadUserGroups();
        });
    }

    async loadUserGroups() {
        const splittedClassName = this.props.viewClassName !== null ? this.props.viewClassName.split(' '): [];
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
