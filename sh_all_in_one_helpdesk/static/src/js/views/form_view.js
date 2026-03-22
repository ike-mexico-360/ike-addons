/** @odoo-module **/

import { FormRenderer } from "@web/views/form/form_renderer";
import { formView } from "@web/views/form/form_view";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class HelpdeskFormRenderer extends FormRenderer {

    setup() {
        super.setup();
        var uid = user.userId
        var ticket = this.props.record.evalContext.id
        this.orm = useService("orm");

        onWillStart(async () => {
            await this.orm.call("sh.helpdesk.ticket", "update_ticket_read_data", [ticket, uid]);
        });
    }
}

export const HelpdeskFormView = {
    ...formView,
    Renderer: HelpdeskFormRenderer,

};

registry.category("views").add("sh_helpdesk_ticket_form_view", HelpdeskFormView);