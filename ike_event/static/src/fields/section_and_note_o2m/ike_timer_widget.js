import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { Component, onError, onWillStart, onWillUnmount, useState } from "@odoo/owl";


export class IkeTimerWidget extends Component {
    static template = "ike_event.IkeTimerWidget";
    static props = {
        ...standardWidgetProps,
    };
    static defaultProps = {
    };
    setup() {
        // console.log("LineTimerWidget", this);
        this.orm = this.env.services.orm;
        this.notification = this.env.services.notification;
        this.resId = null;
        this.interval = null;
        this.state = useState({
            current_state: null,
            seconds: 0,
            paused: false,
            blocked: false,
            is_manual: null,
            assignation_type: 'electronic',
        });
        this.configurationLoaded = false;
        this.configuration = [];

        onWillStart(async () => {
            // console.log("onWillStart");
            // this.test = this.orm.searchRead("")
        })

        useRecordObserver(async (record) => {
            // console.log("useRecordObserver", record.data.state);
            let changed = false;
            if (this.resId != record.resId || this.state.current_state != record.data.state) {
                changed = true
            }
            this.resId = record.resId;
            this.timer_duration = record.data.timer_duration;
            this.state.current_state = record.data.state;
            this.state.is_manual = record.data.is_manual;
            this.state.assignation_type = record.data.assignation_type;
            this.notification_date = record.data.notification_date;
            this.acceptance_date = record.data.acceptance_date;
            this.rejection_date = record.data.rejection_date;
            this.elapsed_time_s = record.data.elapsed_time_s;

            if (changed) {
                switch (this.state.current_state) {
                    case 'available':
                        this.state.seconds = 0;
                        this.processed_date = null;
                        break;
                    case 'notified':
                        if (!this.interval) {
                            this.calculateElapsedTime();
                            this.startTimer();
                        }
                        break;
                    case 'accepted':
                        this.processed_date = this.acceptance_date;
                        this.calculateElapsedTime();
                        this.stopTimer();
                        break;
                    case 'rejected':
                    case 'timeout':
                    case 'expired':
                    case 'cancel':
                        this.processed_date = this.rejection_date;
                        this.calculateElapsedTime();
                        this.stopTimer();
                        break;
                }
            }
            this.state.blocked = false;
        });

        onWillUnmount(() => {
            if (this.interval) {
                this.env.bus.trigger("IKE_EVENT_SYSTRAY:SUPPLIER_TIMEOUT", {
                    payload: {
                        line_id: this.resId,
                        timer_duration: this.timer_duration - this.state.seconds,
                    },
                    sender: this,
                });
            }
            this.stopTimer();
        });

        onError((error) => {
            console.error("time_widget onError", error, this);
        });
    }

    calculateElapsedTime() {
        if (this.elapsed_time_s) {
            this.state.seconds = this.elapsed_time_s;
        }
        // if (this.notification_date) {
        //     const notificationDate = this.notification_date ? this.notification_date.toJSDate() : null;
        //     const currentTime = this.processed_date || Date.now();
        //     const elapsed = Math.floor((currentTime - notificationDate) / 1000);
        //     this.state.seconds = elapsed;
        // }
    }
    startTimer() {
        // console.log("startTimer", this.interval);
        if (!this.interval && this.resId && this.state.current_state == 'notified') {
            this.interval = setInterval(() => {
                try {
                    this.state.seconds += 1;
                    if (this.state.seconds >= this.timer_duration) {
                        this.onTimeout();
                    }
                } catch (err) {
                    console.err("timer_systray", err);
                }
            }, 1000);
        }
    }
    stopTimer() {
        // console.log("stopTimer", this.interval);
        if (this.interval) {
            clearInterval(this.interval);
            this.interval = null;
        }
    }

    async onReset() {
        if (this.state.blocked) {
            return;
        }
        this.stopTimer();
        this.state.blocked = true;
        await this._executeAction(this.props.record, "action_reset");
    }
    async onNotify() {
        if (this.state.blocked) {
            return;
        }
        this.state.blocked = true;
        await this._executeAction(this.props.record, "action_notify");
        this.state.current_state = 'notified';
        this.state.seconds = 0;
        this.startTimer();
    }
    async onAccept() {
        if (this.state.blocked) {
            return;
        }
        this.state.blocked = true;
        await this._executeAction(this.props.record, "action_accept");
        this.stopTimer();
    }
    async onReject() {
        if (this.state.blocked) {
            return;
        }
        this.state.blocked = true;
        await this._executeAction(this.props.record, "action_reject");
        this.stopTimer();
    }
    async onResume() {
        this.state.paused = false;
    }
    async onPlay() {
        this.state.paused = false;
    }
    async onPause() {
        this.state.paused = true;
    }
    async onTimeout() {
        this.stopTimer();
        await this._executeAction(this.props.record, "action_timeout");
        const msg = this.props.record.data.name;
        this.notification.add(msg, {
            title: _t("Timeout"),
            type: "info",
            sticky: false,
        });
    }

    formatTime(seconds) {
        seconds = Math.max(seconds, 0);
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    getTimerClass() {
        let classes = [];
        switch (this.state.current_state) {
            case 'notified':
                if (this.state.seconds >= this.timer_duration - 10) {
                    classes.push('text-danger fw-bold');
                } else if (this.state.seconds >= this.timer_duration - 20) {
                    classes.push('text-warning fw-bold');
                }
                break;
            case 'accepted':
                classes.push("text-success fw-bold");
                break;
            case 'rejected':
            case 'cancel':
                classes.push("text-danger");
                break;
            case 'timeout':
            case 'expired':
                classes.push("text-muted");
                break;
        }
        return classes.join(" ");
    }

    async _executeAction(record, method) {
        const resModel = record.resModel;
        const context = {
            ...record.context,
            not_notify_next: this.state.paused,
        };
        try {
            await rpc(`/web/dataset/call_button/${resModel}/${method}`, {
                args: [[record.resId]],
                kwargs: { context },
                method: method,
                model: resModel,
            });
        } catch (err) {
            console.info("IkeTimerWidget - ExecuteAction", err.data);
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.notification.add(message, { type: "warning" });
            }
            this.state.blocked = false;
        }
        // await record.load();
    }

    get showReset() {
        return odoo.debug && !['available', 'notified'].includes(this.state.current_state);
    }
    get showNotification() {
        return this.state.current_state == 'available' && (this.state.is_manual || this.state.assignation_type == 'manual');
    }
};

export const ikeTimerWidget = {
    component: IkeTimerWidget,
    extractProps: ({ attrs }) => ({}),
};

registry.category("view_widgets").add("ike_timer_widget", ikeTimerWidget);
