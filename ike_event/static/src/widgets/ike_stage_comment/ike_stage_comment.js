import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { Component, onWillUnmount, useState } from "@odoo/owl";

const MINUTE_M_SECONDS = 60000; // For testing purposes


export class IkeStageTrackingComment extends Component {
    static template = "ike_event.IkeStageTrackingComment";
    static props = {
        ...standardWidgetProps,
    };
    static defaultProps = {};
    setup() {
        // console.log("IkeStageTrackingComment", this);
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({
            maxWaitTimeElapsedMinutes: 0,
            maxWaitTimeWarning: false,
            trackingTimeElapsedMinutes: 0,
            trackingTimeWarning: false,
        });
        this.maxWaitTimeInterval = null;
        this.trackingTimeInterval = null;

        this.lastEventStageComment = null;

        useRecordObserver(async (record) => {
            // console.log("useRecordObserver", record);
            this.max_wait_time = this.props.record.data['stage_apply_max_wait_time'] ? this.props.record.data['stage_max_wait_time_minutes'] : null;
            this.tracking_time = this.props.record.data['stage_apply_tracking_time'] ? this.props.record.data['stage_tracking_time_minutes'] : null;
            this.state.maxWaitTimeElapsedMinutes = this.props.record.data['current_elapsed_time_minutes'];
            this.state.trackingTimeElapsedMinutes = this.props.record.data['current_elapsed_time_minutes'];
            if (this.max_wait_time) {
                if (this.state.maxWaitTimeElapsedMinutes >= this.max_wait_time) {
                    this.state.maxWaitTimeWarning = true;
                } else {
                    this.startMaxWaitTimeTimer();
                }
            }
            if (this.tracking_time) {
                const comments = await this.orm.searchRead(
                    "ike.event.stage.comment",
                    [['event_id', '=', this.props.record.resId], ['stage_id', '=', this.props.record.data.stage_id[0]]],
                    ['elapsed_time_minutes', 'sequence', 'create_date'],
                    {
                        order: 'sequence desc',
                        limit: 1,
                    },
                );
                // console.log("comments", comments);
                if (comments && comments.length) {
                    this.lastEventStageComment = comments[0];
                    this.state.trackingTimeElapsedMinutes = this.lastEventStageComment['elapsed_time_minutes'];
                }
                if (this.state.trackingTimeElapsedMinutes >= this.tracking_time) {
                    this.state.trackingTimeWarning = true;
                } else {
                    this.startTrackingTimeTimer();
                }
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
                this.state.maxWaitTimeElapsedMinutes += 1;
                // console.log("minutes", this.state.maxWaitTimeElapsedMinutes);
                if (this.state.maxWaitTimeElapsedMinutes >= this.max_wait_time) {
                    this.state.maxWaitTimeWarning = true;
                    this.stopMaxWaitTimeTimer();
                }
            } catch (err) {
                console.err("startMaxWaitTimeTimer", err);
            }
        }, MINUTE_M_SECONDS);
    }
    stopMaxWaitTimeTimer() {
        if (this.maxWaitTimeInterval) {
            clearInterval(this.maxWaitTimeInterval);
            this.maxWaitTimeInterval = null;
        }
    }
    startTrackingTimeTimer() {
        this.stopTrackingTimeTimer()
        this.trackingTimeInterval = setInterval(() => {
            try {
                this.state.trackingTimeElapsedMinutes += 1;
                // console.log("minutes", this.state.maxWaitTimeElapsedMinutes);
                if (this.state.trackingTimeElapsedMinutes >= this.tracking_time) {
                    this.state.trackingTimeWarning = true;
                    this.stopTrackingTimeTimer();
                }
            } catch (err) {
                console.err("startTrackingTimeTimer", err);
            }
        }, MINUTE_M_SECONDS);
    }
    stopTrackingTimeTimer() {
        if (this.maxWaitTimeInterval) {
            clearInterval(this.maxWaitTimeInterval);
            this.maxWaitTimeInterval = null;
        }
    }
    openCommentForm() {
        let sequence = 1
        let previous_date = this.props.record.data.current_stage_date.toUTC().toFormat("yyyy-MM-dd HH:mm:ss");
        if (this.lastEventStageComment) {
            sequence = this.lastEventStageComment["sequence"] + 1;
            previous_date = this.lastEventStageComment["create_date"];
        }
        const ike_uuid = this.props.record.context.ike_uuid;
        let context = {
            default_event_id: this.props.record.resId,
            default_stage_id: this.props.record.data.stage_id[0],
            default_sequence: sequence,
            default_previous_date: previous_date,
            ike_uuid: ike_uuid,
            // no_create: !this.state.trackingTimeWarning,
        }
        let trackingTimeWarning = this.state.trackingTimeWarning;
        // console.log("context", context);
        this.dialog.add(FormViewDialog, {
            title: _t("Tracking Log"),
            resId: false,
            resModel: "ike.event.stage.comment",
            context: context,
            onRecordSaved: async (record) => {
                // console.log("onRecordSave", record);
                if (trackingTimeWarning) {
                    let lastRecord = record;
                    const recordsLen = record.data.stage_comment_ids.records.length;
                    if (recordsLen) {
                        lastRecord = record.data.stage_comment_ids.records[recordsLen - 1];
                    }
                    this.lastEventStageComment = {
                        id: lastRecord.resId,
                        sequence: lastRecord.data.sequence,
                        elapsed_time_minutes: lastRecord.data.elapsed_time_minutes,
                        create_date: lastRecord.data.create_date.toUTC().toFormat("yyyy-MM-dd HH:mm:ss"),
                    };
                    this.state.trackingTimeWarning = false;
                    this.state.trackingTimeElapsedMinutes = this.lastEventStageComment['elapsed_time_minutes'];
                    this.startTrackingTimeTimer();
                }
            },
            onRecordDiscarded: () => {
                // console.log("onRecordDiscarded", this);
                if (trackingTimeWarning) {
                    this.orm.searchRead(
                        "ike.event.stage.comment",
                        [
                            ['id', '!=', this.lastEventStageComment ? this.lastEventStageComment['id'] : 0],
                            ['event_id', '=', this.props.record.resId],
                            ['stage_id', '=', this.props.record.data.stage_id[0]]],
                        ['elapsed_time_minutes', 'sequence', 'create_date'],
                        {
                            order: 'sequence desc',
                            limit: 1,
                        },
                    ).then(comments => {
                        if (comments && comments.length) {
                            this.lastEventStageComment = comments[0];
                            this.state.trackingTimeElapsedMinutes = this.lastEventStageComment['elapsed_time_minutes'];
                        }
                        if (this.state.trackingTimeElapsedMinutes >= this.tracking_time) {
                            this.state.trackingTimeWarning = true;
                        } else {
                            this.state.trackingTimeWarning = false;
                            this.startTrackingTimeTimer();
                        }
                    });
                }
            },
            close: () => {
                // console.log("close", this);
            }
        }, {
            onClose: () => {
                // console.log("onClose", this);
            }
        });
    }
};

export const ikeStageTrackingComment = {
    component: IkeStageTrackingComment,
};

registry.category("view_widgets").add("ike_stage_tracking_comment", ikeStageTrackingComment);
