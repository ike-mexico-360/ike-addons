/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { ListController } from '@web/views/list/list_controller';
import { listView } from "@web/views/list/list_view";

import { IkeEventScreenListRenderer } from "./ike_event_screen_list_renderer";


export class IkeEventListController extends ListController {
    setup() {
        // console.log("IkeEventList", this);
        super.setup();
        this.notification = this.env.services.notification;

        useBus(this.env.bus, "IKE_EVENT_SYSTRAY:EVENT_LIST_RELOAD", (event) => {
            this.broadcastEventListReload(event.detail.payload)
        });
    }
    broadcastEventListReload(payload) {
        // console.log("broadcastEventListReload", payload);
        if (!payload || !payload.data || !payload.data.length) {
            return;
        }
        for (const item of payload.data) {
            const record = this.model.root.records.find(rec => rec.resId == item.id);
            if (record && record.data.stage_ref != item.stage_red) {
                record.load();
            }
        }
    }
    async _executeAction(record, method, params = null) {
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
            console.error("IkeEventList - ExecuteAction", err.data);
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.notification.add(message, { type: "warning" });
            }
        }
        await record.load();
    }
};

export const ikeEventScreenListView = {
    ...listView,
    Renderer: IkeEventScreenListRenderer,
    Controller: IkeEventListController,
};

registry.category("views").add("ike_event_screen_list", ikeEventScreenListView);
