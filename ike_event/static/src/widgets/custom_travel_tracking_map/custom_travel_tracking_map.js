import { Component, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from '@web/core/l10n/translation';

export class IkeTravelTrackingMap extends Component {
    static template = "ike_event.IkeTravelTrackingMap";

    static props = {
        ...standardFieldProps,
    };

    setup() {
        super.setup();
        this.action = useService("action");
        this.state = useState({
            url: this.props.record.data[this.props.name] || "",
        });
    }
}

export const ikeTravelTrackingMap = {
    component: IkeTravelTrackingMap,
    additionalClasses: ["ike_travel_tracking_map_container"],
};

registry.category("fields").add("ike_iframe_travel_tracking_map", ikeTravelTrackingMap);
