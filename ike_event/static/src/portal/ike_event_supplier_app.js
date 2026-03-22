
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";

import { Component, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";

const IKE_EVENT_CHANNEL = "ike_channel_event_";
const IKE_SUPPLIER_CHANNEL = "ike_channel_supplier_";


export class IkeEventSupplierApp extends Component {
    static template = "ike_event.IkeEventSupplierApp";
    static props = {
        word: { type: String, optional: true },
    };

    setup() {
        console.log("IkeEventSupplierApp", this, this.env.services);
        this.busService = this.env.services.bus_service;
        this.notification = this.env.services.notification;
        this.orm = this.env.services.orm;

        this.state = useState({
            channel_supplier_id: null,
            channel_event_id: null,
            event: null,
            eventSupplierLines: null,
            use_public_model: false,
        });

        this.broadcastEventSupplierReload = (payload) => {
            console.log("broadcastEventSupplierReload", payload);
            const data = payload.data.filter(item => item.event_id[0] == parseInt(this.state.channel_event_id));
            const reload_event = data.find(item => item.event_reload);
            if (reload_event) {
                // Reload
                this.setEvent();
                return;
            }
            for (let item of data) {
                const service_supplier_id = this.state.event.service_supplier_ids.find(x => x.id == item.id);
                if (service_supplier_id) {
                    // Load
                    service_supplier_id.load();
                    // Notification
                    const title = `EVENT: ${item.event_id[1]}`;
                    const message = `Supplier ${item.supplier_id[1]}: ${item.state}`;
                    this.notification.add(message, {
                        title: title,
                        type: "info",
                        sticky: true,
                    });
                }
            }
        };
        this.broadcastEventListReload = (payload) => {
            console.log("broadcastEventListReload", payload);
        };
        this.broadcastSupplier = (payload) => {
            console.log("broadcastSupplier", payload);
            const data = payload.data;
            for (let item of data) {
                const service_supplier_id = this.state.eventSupplierLines.find(x => x.id == item.id);
                if (service_supplier_id) {
                    // Load
                    service_supplier_id.load();
                    // Notification
                    const title = `EVENT: ${item.event_id[1]}`;
                    const message = `Supplier ${item.supplier_id[1]}: ${item.state}`;
                    this.notification.add(message, {
                        title: title,
                        type: "success",
                        sticky: true,
                    });
                }
            }
        }

        // Subscriptions
        this.busService.subscribe("ike_event_supplier_reload", this.broadcastEventSupplierReload);
        this.busService.subscribe("ike_supplier_lines_reload_2", this.broadcastSupplier);
        this.busService.subscribe("IKE_CHANNEL_LIST_LISTEN", this.broadcastSupplier);

        onMounted(() => {
            this.busService.addChannel("IKE_CHANNEL_LIST");
        });
        onWillUnmount(() => {
            this._unsubscribe();
            this.busService.deleteChannel("IKE_CHANNEL_LIST");
            this.busService.unsubscribe("IKE_CHANNEL_LIST_LISTEN", this.broadcastSupplier);
        });
    }
    async subscribeEvent() {
        this.unsubscribeEvent();
        this.busService.addChannel(IKE_EVENT_CHANNEL + this.state.channel_event_id);
        this.setEvent();
    }
    subscribeSupplier() {
        this.checkSupplier(this.state.channel_supplier_id);
        this.unsubscribeSupplier();
        this.busService.addChannel(IKE_SUPPLIER_CHANNEL + this.state.channel_supplier_id);
        this.setEventSupplierLines();
    }
    unsubscribeEvent() {
        if (this.state.channel_event_id) {
            this.busService.deleteChannel(IKE_EVENT_CHANNEL + this.state.channel_event_id);
        }
    }
    unsubscribeSupplier() {
        if (this.state.channel_supplier_id) {
            this.busService.deleteChannel(IKE_SUPPLIER_CHANNEL + this.state.channel_supplier_id);
        }
    }
    _unsubscribe() {
        // Delete channels
        this.unsubscribeEvent();
        this.unsubscribeEvent();

        // Unsubscribe
        this.busService.unsubscribe("ike_event_supplier_reload", this.broadcastSupplier);
        this.busService.unsubscribe("ike_supplier_lines_reload_2", this.broadcastSupplier);
    }
    async checkSupplier(supplierId) {
        const result = await this.orm.searchRead(
            "res.partner.supplier_users.rel",
            [
                ["user_id", "=", user.userId],
                ["supplier_id", "=", supplierId],
            ],
            ["id"]
        );
        if (!result.length) {
            this.notification.add("You do not have access to notifications from this supplier.", {
                type: "warning",
            })
        }
    }
    async getServiceSupplier(id) {
        const result = await this.orm.webSearchRead(
            this.getEventSupplierModel(),
            [["id", "=", id]],
            {
                specification: {
                    id: {},
                    supplier_id: {
                        fields: {
                            id: {},
                            name: {}
                        }
                    },
                    state: {},
                    stage_ref: {},
                }
            },
        );
        if (result.length) {
            return result.records[0];
        }
        return {};
    }
    async _executeAction(resModel, resId, action_name) {
        try {
            const result = await this.orm.call(
                resModel,
                action_name,
                [resId]
            );
            return result;
        } catch (err) {
            console.error("Orm Call", err.data);
            if (err.data?.name) {
                const title = err.data.name;
                const message = err.data.message;
                this.notification.add(message, {
                    title: title,
                    type: "warning"
                });
            }
        }
    }
    async actionReset(id) {
        const result = this._executeAction(this.getEventSupplierModel(), id, "action_reset");
    }
    async actionNotify(id) {
        const result = this._executeAction(this.getEventSupplierModel(), id, "action_notify");
    }
    async actionAccept(id) {
        const result = this._executeAction(this.getEventSupplierModel(), id, "action_accept");
    }
    async actionReject(id) {
        const result = this._executeAction(this.getEventSupplierModel(), id, "action_reject");
    }
    showReset(service_supplier_id) {
        return ["accepted", "assigned", "rejected", "timeout"].includes(service_supplier_id.state);
    }
    showNotify(service_supplier_id) {
        return service_supplier_id.state == "available";
    }
    showAcceptReject(service_supplier_id) {
        return service_supplier_id.state == "notified";
    }
    async setEvent() {
        const result = await this.orm.webSearchRead(
            this.getEventModel(), [["id", "=", this.state.channel_event_id]], {
            specification: {
                id: {},
                display_name: {},
                stage_ref: {},
                service_supplier_ids: {
                    fields: {
                        id: {},
                        supplier_id: {
                            fields: {
                                name: {}
                            }
                        },
                        state: {},
                        stage_ref: {},
                    }
                },
            },
        });
        if (result.records.length) {
            const record = result.records[0];
            for (let i = 0; i < record.service_supplier_ids.length; i++) {
                let item = record.service_supplier_ids[i];
                item.load = async () => {
                    const data = await this.getServiceSupplier(item.id);
                    this.state.event.service_supplier_ids[i] = {
                        ...data,
                        changed: true,
                        load: item.load,
                    };
                    setTimeout(() => {
                        this.state.event.service_supplier_ids[i]["changed"] = false;
                    }, 7000);
                };
            }
            this.state.event = record;
        }
    }
    async setEventSupplierLines() {
        const result = await this.orm.webSearchRead(
            this.getEventSupplierModel(),
            [
                ["supplier_id", "=", parseInt(this.state.channel_supplier_id)],
                ["stage_ref", "not in", ["finalized", "cancel"]],
            ], {
            specification: {
                id: {},
                supplier_id: {
                    fields: {
                        id: {},
                        name: {}
                    }
                },
                event_id: {
                    fields: {
                        name: {},
                    },
                },
                state: {},
                stage_ref: {},
            },
            limit: 20,
        });
        if (result.records.length) {
            for (let i = 0; i < result.records.length; i++) {
                let item = result.records[i];
                item.load = async () => {
                    const data = await this.getServiceSupplier(item.id);
                    this.state.eventSupplierLines[i]["state"] = data.state;
                    this.state.eventSupplierLines[i]["stage_ref"] = data.stage_ref;
                    this.state.eventSupplierLines[i]["changed"] = true;
                    setTimeout(() => {
                        this.state.eventSupplierLines[i]["changed"] = false;
                    }, 7000);
                };
            }
            this.state.eventSupplierLines = result.records;
        }
    }
    getEventModel() {
        return "ike.event" + (this.state.use_public_model ? ".public" : "");
    }
    getEventSupplierModel() {
        return "ike.event.supplier" + (this.state.use_public_model ? ".public" : "");
    }
}

registry.category("public_components").add("ike_event.IkeEventSupplierApp", IkeEventSupplierApp);
