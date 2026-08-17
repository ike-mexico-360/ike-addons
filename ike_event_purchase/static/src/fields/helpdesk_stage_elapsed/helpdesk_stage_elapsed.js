import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, onWillUnmount, useState } from "@odoo/owl";


export class HelpdeskStageElapsed extends Component {
    static template = "ike_event_purchase.HelpdeskStageElapsed";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({
            elapsedSeconds: 0,
            valueFormatted: "",
            maxWaitTimeWarning: false,
        });
        this.timer = null;

        useRecordObserver((record) => {
            this.stopTimer();
            this.maxWaitTimeSeconds = (
                record.data.x_stage_max_wait_time_minutes || 0
            ) * 60;
            this.state.elapsedSeconds = record.data.current_elapsed_time_seconds || 0;
            this.state.maxWaitTimeWarning = Boolean(
                this.maxWaitTimeSeconds
                && this.state.elapsedSeconds >= this.maxWaitTimeSeconds
            );

            if (this.maxWaitTimeSeconds) {
                this.state.valueFormatted = this.formatElapsedTime(
                    this.state.elapsedSeconds
                );
                this.startTimer();
            } else {
                this.state.valueFormatted = "";
            }
        });

        onWillUnmount(() => this.stopTimer());
    }

    startTimer() {
        this.timer = setInterval(() => {
            this.state.elapsedSeconds += 1;
            this.state.valueFormatted = this.formatElapsedTime(
                this.state.elapsedSeconds
            );
            this.state.maxWaitTimeWarning = Boolean(
                this.maxWaitTimeSeconds
                && this.state.elapsedSeconds >= this.maxWaitTimeSeconds
            );
        }, 1000);
    }

    stopTimer() {
        if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    formatElapsedTime(totalSeconds) {
        totalSeconds = Math.max(Math.round(totalSeconds), 0);
        const days = Math.floor(totalSeconds / 86400);

        if (days > 0) {
            const dayText = _t("day");
            return `${days} ${dayText}${days === 1 ? "" : "s"}`;
        }

        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        if (hours > 0) {
            return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
        }
        return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
    }
}

export const helpdeskStageElapsed = {
    component: HelpdeskStageElapsed,
};

registry.category("fields").add("helpdesk_stage_elapsed", helpdeskStageElapsed);
