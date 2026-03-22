/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/** Main Component **/
class TicketPopoverWidget extends Component {
    static template = "sh_all_in_one_helpdesk.TicketPopoverWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ tickets: [], visible: false, count: 0 });
        this.action = useService("action");
        this.onClickEditActivityButton = this.onClickEditActivityButton.bind(this);

        // Determine the record type (sale.order or purchase.order)
        this.modelName = this.props.record.resModel;
        this.resId = this.props.record.resId;

        // Determine the field name for tickets based on the model
        if (this.modelName === 'sale.order') {
            this.ticketIdsFieldName = 'sh_sale_ticket_ids';
            this.defaultLinkFieldName = 'default_sh_sale_order_ids';
        } else if (this.modelName === 'purchase.order') {
            this.ticketIdsFieldName = 'sh_purchase_ticket_ids';
            this.defaultLinkFieldName = 'default_sh_purchase_order_ids';
        }else if (this.modelName === 'account.move') {
            this.ticketIdsFieldName = 'sh_ticket_ids';
            this.defaultLinkFieldName = 'default_sh_invoice_ids';
        }else if (this.modelName === 'crm.lead') {
            this.ticketIdsFieldName = 'sh_ticket_ids';
            this.defaultLinkFieldName = 'default_sh_lead_ids';
        }else if (this.modelName === 'repair.order') {
            this.ticketIdsFieldName = 'sh_repair_ticket_ids';
            this.defaultLinkFieldName = 'default_sh_repair_order_ids';
        } else {
            console.warn(`TicketPopoverWidget: Unsupported model ${this.modelName}.`);
            this.ticketIdsFieldName = null;
            this.defaultLinkFieldName = null;
        }

        if (this.ticketIdsFieldName) {
            this.loadTicketCount();  // Fetch count on load
        }
    }

    async onClick(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        if (!this.ticketIdsFieldName) {
            console.warn("Ticket field name not determined for this model.");
            return;
        }

        const rawTickets = this.props.record.data[this.ticketIdsFieldName];
        let ticketIds = [];

        if (rawTickets?.resIds) {
            ticketIds = rawTickets.resIds;
        } else if (Array.isArray(rawTickets)) {
            ticketIds = [...rawTickets];
        }
        if (typeof ticketIds === "object" && ticketIds !== null) {
            ticketIds = Array.from(ticketIds);
        }

        if (!ticketIds.length) {
            console.warn("No related tickets found.");
            // return; // Uncomment this if you don't want the popover to show when no tickets
        }

        const tickets = await this.orm.read("sh.helpdesk.ticket", ticketIds, ["name", "partner_id", "email_subject", "stage_id"]);
        this.state.tickets = tickets;
        this.state.visible = true;

        const hide = () => {
            this.state.visible = false;
            document.removeEventListener("click", hide);
        };
        setTimeout(() => {
            document.addEventListener("click", hide);
        }, 0);
    }

    async loadTicketCount() {
        const rawTickets = this.props.record.data[this.ticketIdsFieldName];
        let ticketIds = [];

        if (rawTickets?.resIds) {
            ticketIds = rawTickets.resIds;
        } else if (Array.isArray(rawTickets)) {
            ticketIds = [...rawTickets];
        }

        if (typeof ticketIds === "object" && ticketIds !== null) {
            ticketIds = Array.from(ticketIds);
        }

        this.state.count = ticketIds.length;
    }

    async onClickAddTicketButton(ev) {
        if (this.state.visible) {
            ev.stopPropagation();
            ev.preventDefault();

            if (!this.resId || !this.defaultLinkFieldName) {
                console.warn("Missing record ID or default link field name.");
                return;
            }

            const context = {
                [this.defaultLinkFieldName]: [this.resId], // Dynamically set based on model
                default_partner_id: this.props.record.data.partner_id?.[0],
                default_user_id: this.props.record.data.user_id?.[0],
            };

            await this.action.doAction({
                type: "ir.actions.act_window",
                name: "Create Ticket",
                res_model: "sh.helpdesk.ticket",
                views: [[false, "form"]],
                target: "new",
                context,
                mode: "edit",
            });
        }
    }

    async onClickEditActivityButton(ticketId) {
        if (!ticketId) {
            console.warn("No ticket ID provided");
            return;
        }

        await this.action.doAction({
            type: "ir.actions.act_window",
            name: "Edit Ticket",
            res_model: "sh.helpdesk.ticket",
            res_id: ticketId,
            views: [[false, "form"]],
            target: "new",  // Important to open as modal
        });
    }
}

export const ticketActivity = {
    component: TicketPopoverWidget,
    displayName: ("Ticket Popover"),
    supportedTypes: ["integer", "many2many"],
};

registry.category("fields").add("ticket_popover_widget", ticketActivity);