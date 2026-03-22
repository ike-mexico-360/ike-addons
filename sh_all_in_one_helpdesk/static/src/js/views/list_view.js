/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { listView } from "@web/views/list/list_view";

export class HelpdeskListRenderer extends ListRenderer {
    

    // Replace this method
    getRowClass(record) {

        // Odoo code
        // classnames coming from decorations
        const classNames = this.props.archInfo.decorations
            .filter((decoration) => evaluateExpr(decoration.condition, record.evalContextWithVirtualIds))
            .map((decoration) => decoration.class);

        if (record.selected) {
            classNames.push("table-info");
        }
        // "o_selected_row" classname for the potential row in edition
        if (record.isInEdition) {
            classNames.push("o_selected_row");
        }
        if (record.selected) {
            classNames.push("o_data_row_selected");
        }
        if (this.canResequenceRows) {
            classNames.push("o_row_draggable");
        }
        // Odoo code


        // SH code
        const uid = user.userId;
        const ticket_read_data = record._values.ticket_read_data;

        if (ticket_read_data && uid) {
            const ticketList = JSON.parse(ticket_read_data);

            if (ticketList && !ticketList.includes(uid)) {
                classNames.push('sh_data_row_readble_line');
            }
        }
        else {
            classNames.push('sh_data_row_readble_line');
        }
        // SH code


        return classNames.join(" ");
    }



}

export const HelpdeskListView = {
    ...listView,
    Renderer: HelpdeskListRenderer,

};

registry.category("views").add("sh_helpdesk_ticket_list_view", HelpdeskListView);