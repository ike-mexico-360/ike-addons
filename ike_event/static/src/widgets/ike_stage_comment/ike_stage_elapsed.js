import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, onWillUnmount, useState } from "@odoo/owl";


export class IkeStageElapsed extends Component {
    static template = "ike_event.IkeStageElapsed";
    static props = {
        ...standardFieldProps,
    };
    static defaultProps = {};
    setup() {
        console.log("IkeStageElapsed", this);
        this.state = useState({
            elapsedSeconds: 0,
            valueFormatted: 0,
            maxWaitTimeWarning: false,
        });
        this.maxWaitTimeInterval = null;

        useRecordObserver(async (record) => {
            this.max_wait_time = (this.props.record.data['stage_max_wait_time_minutes'] || 0) * 60;
            this.tracking_time = (this.props.record.data['stage_tracking_time_minutes'] || 0) * 60.0;
            this.state.elapsedSeconds = this.props.record.data['current_elapsed_time_seconds'];
            if (this.max_wait_time || this.tracking_time) {
                this.state.valueFormatted = this.getValueFormatted(this.state.elapsedSeconds);
                if (this.state.elapsedSeconds / 86400 < 1) {
                    this.startMaxWaitTimeTimer();
                } else {
                    if (this.max_wait_time && this.state.elapsedSeconds >= this.max_wait_time) {
                        this.state.maxWaitTimeWarning = true;
                    }
                }
            } else {
                this.state.valueFormatted = "";
            }
        });

        onWillUnmount(() => {
            this.stopMaxWaitTimeTimer();
        });
    }
    startMaxWaitTimeTimer() {
        this.stopMaxWaitTimeTimer()
        this.maxWaitTimeInterval = setInterval(() => {
            try {
                this.state.elapsedSeconds += 1;
                this.state.valueFormatted = this.getValueFormatted(this.state.elapsedSeconds);
                // console.log(this.state.elapsedSeconds, this.state.valueFormatted);
                if (this.max_wait_time && this.state.elapsedSeconds >= this.max_wait_time) {
                    this.state.maxWaitTimeWarning = true;
                }

            } catch (err) {
                console.err("startMaxWaitTimeTimer", err);
            }
        }, 1000);
    }
    stopMaxWaitTimeTimer() {
        if (this.maxWaitTimeInterval) {
            clearInterval(this.maxWaitTimeInterval);
            this.maxWaitTimeInterval = null;
        }
    }
    getValueFormatted(totalSeconds) {
        totalSeconds = Math.round(totalSeconds);

        const days = Math.floor(totalSeconds / 86400);
        const dayText = _t("day");

        if (days > 0) {
            return `${days} ${dayText}${days === 1 ? '' : 's'}`;
        }

        const hours = Math.floor(totalSeconds / 3600);
        const minutes = Math.floor((totalSeconds % 3600) / 60);
        const seconds = totalSeconds % 60;

        if (hours > 0) {
            return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }

        return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    }
};

export const ikeStageElapsed = {
    component: IkeStageElapsed,
};

registry.category("fields").add("ike_stage_elapsed", ikeStageElapsed);
