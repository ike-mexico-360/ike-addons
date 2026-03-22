/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { IkeAffiliations } from "../ike_affiliations_widget/ike_affiliations_widget";
import { IkeComponentInfo } from "./components/ike_component_info";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";


export class IkeEventScreenHeaderInfo extends Component {
    static template = "ike_event.IkeEventScreenHeaderInfo";
    static components = { IkeComponentInfo, IkeAffiliations };
    static props = {
        ...standardWidgetProps,
        record: { type: Object, optional: false },
    };

    get summary() {
        const sections = this.props.record.data.sections;
        if (sections === undefined || sections === null) {
            return { top: [], bottom: [] };
        }
        if (sections.summary === undefined || sections.summary === null) {
            return { top: [], bottom: [] };
        }
        if (sections.summary.top === undefined || sections.summary.top === null) {
            sections.summary.top = [];
        }
        if (sections.summary.bottom === undefined || sections.summary.bottom === null) {
            sections.summary.bottom = [];
        }
        return sections.summary;
    }

    get topFields() {
        return this.summary.top;
    }

    get bottomFields() {
        return this.summary.bottom;
    }

    get record() {
        return this.props.record;
    }
}

export const ikeEventScreenHeaderInfo = {
    component: IkeEventScreenHeaderInfo,
    additionalClasses: ["o_ike_event_screen_header_info_widget"],
};

registry.category("view_widgets").add("ike_event_screen_header_info", ikeEventScreenHeaderInfo);
