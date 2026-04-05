import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";

import { Component, onError, onMounted, onWillUnmount, useState } from "@odoo/owl";

const CHANNEL_NAME = "ike_channel_event_";
const LIST_CHANNEL_NAME = "IKE_CHANNEL_LIST";
const SUBSCRIPTIONS = {
    "SupplierReload": "ike_event_supplier_reload",
    "NextSearch": "ike_event_next_search",
    "EventReload": "IKE_EVENT_RELOAD",
    "EventListReload": "IKE_CHANNEL_LIST_LISTEN",
};


export class IkeEventSystray extends Component {
    static components = {};
    static props = [];
    static template = "ike_event.IkeEventSystray";

    setup() {
        console.log("IkeEventSystray", this, this.env.services);
        this.busService = this.env.services.bus_service;
        this.notification = this.env.services.notification;

        this.actionService = this.env.services.action;
        this.state = useState({
            resModel: null,
            type: null,
            resId: null,
            eventChannel: null,
            listChannel: null,
        });
        this._updateFromAction = this._updateFromAction.bind(this);

        // Life cycle
        onMounted(() => {
            this._updateFromAction();
            this.env.bus.addEventListener("ACTION_MANAGER:UPDATE", this._updateFromAction);
        });
        onWillUnmount(() => {
            this.env.bus.addEventListener("ACTION_MANAGER:UPDATE", this._updateFromAction);
            for (const id of this._timeouts) {
                clearTimeout(id);
            }
            this._timeouts.clear();
            // Delete Channels
            if (this.state.eventChannel) {
                this.busService.deleteChannel(this.state.eventChannel);
            }
            if (this.state.listChannel) {
                this.busService.deleteChannel(this.state.listChannel);
            }
            // Unsubscribe notifications
            for (let subscription in SUBSCRIPTIONS) {
                this.busService.unsubscribe(SUBSCRIPTIONS[subscription], this.subscriptions[subscription]);
            }
        });
        onError((error) => {
            console.error("ike_event_systray onError", error, this);
        });

        // New Record
        useBus(this.env.bus, "IKE_EVENT_SYSTRAY:NEW_EVENT", (event) => {
            const resId = event.detail.payload.resId;
            if (this.state.resId != resId) {
                if (this.state.eventChannel) {
                    this.busService.deleteChannel(this.state.eventChannel);
                }
                // Add current
                this.state.resId = resId;
                this.state.eventChannel = CHANNEL_NAME + resId;
                this.busService.addChannel(this.state.eventChannel);
            }
        });
        // Timeout
        this._timeouts = new Set();
        useBus(this.env.bus, "IKE_EVENT_SYSTRAY:SUPPLIER_TIMEOUT", (event) => {
            const { payload, sender } = event.detail;

            if (payload?.line_id && payload?.timer_duration) {
                const timeoutId = setTimeout(() => {
                    try {
                        this._timeouts.delete(timeoutId);
                        this._executeTimeoutLine(payload.line_id);
                    } catch (err) {
                        console.err("timer_systray", err);
                    }
                }, (payload.timer_duration + 5) * 1000);

                this._timeouts.add(timeoutId);
            }
        });

        // Subscriptions
        this.subscriptions = {};
        for (let subscription in SUBSCRIPTIONS) {
            this.subscriptions[subscription] = (payload, { id }) => {
                // console.log(subscription, payload, id);
                this["broadcast" + subscription](payload);
            };
            this.busService.subscribe(SUBSCRIPTIONS[subscription], this.subscriptions[subscription]);
        }
    }

    // Notifications
    _updateFromAction(event) {
        // console.log("_updateFromAction", event);
        // Get Info
        const resModel = event?.detail?.componentProps?.resModel || null;
        const type = event?.detail?.componentProps?.type || null;
        const resId = event?.detail?.componentProps?.resId || null;

        if (resModel == "ike.event") {
            if (type == "form") {
                // Remove list channel
                if (this.state.listChannel) {
                    this.busService.deleteChannel(this.state.listChannel);
                }
                // Remove previous
                if (this.state.eventChannel && this.state.resId != resId) {
                    this.busService.deleteChannel(this.state.eventChannel);
                }
                // Add current
                this.state.eventChannel = CHANNEL_NAME + resId;
                this.busService.addChannel(this.state.eventChannel);
            } else if (type == "list") {
                // Remove previous
                if (this.state.eventChannel) {
                    this.busService.deleteChannel(this.state.eventChannel);
                }
                // Add list channel
                if (!this.state.listChannel) {
                    this.state.listChannel = LIST_CHANNEL_NAME;
                    this.busService.addChannel(this.state.listChannel);
                }
            }
        } else {
            if (this.state.eventChannel) {
                this.busService.deleteChannel(this.state.eventChannel);
            }
            if (this.state.listChannel) {
                this.busService.deleteChannel(this.state.listChannel);
            }
        }
        // Update State
        this.state.resModel = resModel;
        this.state.type = type;
        this.state.resId = resId;
    }
    async broadcastSupplierReload(payload) {
        return this._triggerBusEvent("SUPPLIER_RELOAD", payload);
    }
    async broadcastNextSearch(payload) {
        return this._triggerBusEvent("NEXT_SEARCH", payload);
    }
    async broadcastEventListReload(payload) {
        return this._triggerBusEvent("EVENT_LIST_RELOAD", payload);
    }
    async broadcastEventReload(payload) {
        return this._triggerBusEvent("EVENT_RELOAD", payload);
    }
    async _triggerBusEvent(type, payload) {
        // console.log("_triggerBusEvent", type, payload);
        if (this.state.resModel == "ike.event" && this.state.resId) {
            // Form
            this.env.bus.trigger("IKE_EVENT_SYSTRAY:" + type, {
                payload: payload,
                sender: this,
            });
        } else {
            if (type == "SUPPLIER_RELOAD") {
                if (!payload || !payload.data || !payload.data.length) {
                    return;
                }
                // Event Notification
                for (const item of payload.data) {
                    const states_to_notify = ['accepted', 'cancel', 'cancel_supplier'];
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
                                message = `${supplier_name}: ${item.folio}`;
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
                }
            } else if (type == "EVENT_RELOAD") {
                // List
                this.env.bus.trigger("IKE_EVENT_SYSTRAY:" + type, {
                    payload: payload,
                    sender: this,
                });
            }
        }
    }
    async _executeTimeoutLine(line_id) {
        const resModel = "ike.event.supplier";
        const method = "action_timeout";
        const context = {
            not_notify_next: true,
        };
        try {
            await rpc(`/web/dataset/call_button/${resModel}/${method}`, {
                args: [[line_id]],
                kwargs: { context },
                method: method,
                model: resModel,
            });
        } catch (err) {
            console.error("IkeGlobalTimer - onTimeoutLine", err);
        }
    }
}

export const ikeEventSystray = {
    Component: IkeEventSystray,
};

registry
    .category("systray")
    .add("custom_module_testing.ike_event_systray", ikeEventSystray, { sequence: 101 });
