import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { FormController } from '@web/views/form/form_controller';
import { formView } from "@web/views/form/form_view";

import { useEffect } from "@odoo/owl";


export class IkeEventFormController extends FormController {
    setup() {
        console.log("IkeEventForm", this);
        super.setup();
        this.notification = this.env.services.notification;

        // New event
        useEffect((resId) => {
            if (resId) {
                // console.log("resId", resId);
                this.env.bus.trigger("IKE_EVENT_SYSTRAY:NEW_EVENT", {
                    payload: {
                        resId: resId,
                    },
                    sender: this,
                });
            }
        }, () => [this.model.root.resId]);

        useBus(this.env.bus, "IKE_EVENT_SYSTRAY:SUPPLIER_RELOAD", (event) => {
            this.broadcastSupplierReload(event.detail.payload);
        });
        useBus(this.env.bus, "IKE_EVENT_SYSTRAY:NEXT_SEARCH", (event) => {
            this.broadcastNextSearch(event.detail.payload);
        });
        useBus(this.env.bus, "IKE_EVENT_SYSTRAY:EVENT_RELOAD", (event) => {
            this.broadcastEventReload(event.detail.payload);
        });
    }
    async broadcastSupplierReload(payload) {
        if (!payload || !payload.data || !payload.data.length) {
            return;
        }
        const data = payload.data.filter(x => x.event_id[0] == this.model.root.resId);

        if (!data.length) {
            return;
        }

        const reload_item = data.find(x => x.event_reload);
        if (reload_item) {
            await this.model.root.load();
            return;
        }
        for (const item of data) {
            if (item.event_id[0] != this.model.root.resId) {
                continue;
            }
            const line_id = this.model.root.data.service_supplier_ids.records.find(record => record.resId == item.id);

            const states_to_notify = ['accepted', 'rejected', 'cancel', 'cancel_supplier'];
            if (states_to_notify.includes(item.state)) {
                const event_name = item.event_id[1];
                const supplier_name = item.supplier_id[1];
                let message = "";
                let message_options = {
                    title: event_name + ": ",
                    sticky: false,
                };
                switch (item.state) {
                    case 'accepted':
                        message = `${supplier_name}`;
                        message_options.title += _t("Accepted");
                        message_options.type = "success";
                        break;
                    case 'rejected':
                        message = `${supplier_name}`;
                        message_options.title += _t("Rejected");
                        message_options.type = "warning";
                        break;
                    case 'cancel':
                        message = `${supplier_name}`;
                        message_options.title += _t("Cancelled");
                        message_options.type = "danger";
                        message_options.sticky = true;
                        break;
                    case 'cancel_supplier':
                        message = `${supplier_name}`;
                        message_options.title += _t("Cancelled by Supplier");
                        message_options.type = "danger";
                        message_options.sticky = true;
                        break;
                    default:
                        break;
                }
                this.notification.add(message, message_options);
            }

            if (line_id && !item.event_reload) {
                await line_id.load();
            }
        }
    }
    async broadcastNextSearch(payload) {
        if (!payload || payload.id != this.model.root.resId) {
            return;
        }
        const params = payload.params;
        this._executeAction(this.model.root, "next_search_suppliers", params);
    }
    async broadcastEventReload(payload) {
        if (!payload || !payload.data || !payload.data.length) {
            return;
        }
        const data = payload.data.find(x => x.id == this.model.root.resId);
        if (data) {
            // console.log("RELOADED");
            await this.model.root.load();
        }
    }
    async _executeAction(record, method, params) {
        const resModel = record.resModel;
        const context = record.context;
        const args = [[record.resId]];
        if (params) {
            args.push(params);
        }
        try {
            await rpc(`/web/dataset/call_button/${resModel}/${method}`, {
                args: args,
                kwargs: { context },
                method: method,
                model: resModel,
            });
        } catch (err) {
            console.error("IkeEventForm - ExecuteAction", err.data);
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.notification.add(message, { type: "warning" });
            }
        }
        await record.load();
    }
};

export const ikeEventScreenFormView = {
    ...formView,
    Controller: IkeEventFormController,
}

registry.category("views").add("ike_event_form", ikeEventScreenFormView);
