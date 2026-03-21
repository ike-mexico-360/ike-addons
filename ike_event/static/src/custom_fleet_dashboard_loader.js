import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { LazyComponent } from "@web/core/assets";

import { Component, xml } from "@odoo/owl";


class CustomFleetDashboard extends Component { };

CustomFleetDashboard.components = { LazyComponent };
CustomFleetDashboard.props = {
    ...standardActionServiceProps,
};
CustomFleetDashboard.template = xml`
<LazyComponent bundle="'ike_event.custom_fleet_dashboard_bundle'" Component="'CustomFleetDashboard'" props="props"/>
`;

registry.category("actions").add("ike_event.custom_fleet_dashboard_view_action", CustomFleetDashboard);