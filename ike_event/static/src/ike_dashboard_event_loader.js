import { registry } from "@web/core/registry";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { LazyComponent } from "@web/core/assets";

import { Component, xml } from "@odoo/owl";


class IkeDashboardEventLoader extends Component { };

IkeDashboardEventLoader.components = { LazyComponent };
IkeDashboardEventLoader.props = {
    ...standardActionServiceProps,
};
IkeDashboardEventLoader.template = xml`
<LazyComponent bundle="'ike_event.ike_dashboard_event_bundle'" Component="'IkeDashboardEvent'" props="props"/>
`;

registry.category("actions").add("ike_event.ike_dashboard_event_view_action", IkeDashboardEventLoader);
