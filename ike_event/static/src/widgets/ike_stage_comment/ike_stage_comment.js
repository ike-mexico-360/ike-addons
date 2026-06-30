import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useBus, useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import { Component, onWillUnmount, useState } from "@odoo/owl";

const MINUTE_SECONDS = 1000; // For testing purposes


export class IkeStageTrackingComment extends Component {
    static template = "ike_event.IkeStageTrackingComment";
    static props = {
        ...standardFieldProps,
    };
    static defaultProps = {};
    setup() {
        // console.log("IkeStageTrackingComment", this);
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.action = useService("action");

        this.state = useState({
            comments: {}, // {'user': {}, '1': {}, '2': {}}
            trackingTimeWarning: false,
        });
        this.supplierNumbers = []; // [1, 2, 3]
        this.maxWaitTimeInterval = null;
        this.trackingTimeInterval = null;

        useRecordObserver(async (record) => {
            this.supplierNumbers = this.props.record.data['selected_supplier_ids'].records.map(x => x.data.supplier_number);

            this.previous_date = this.props.record.data['current_stage_date'].toUTC().toFormat("yyyy-MM-dd HH:mm:ss");
            this.tracking_time = (this.props.record.data['stage_tracking_time_minutes'] || 0) * 60.0;

            for (const commentRecord of this.props.record.data.current_stage_comment_ids.records) {
                const comment = {
                    id: commentRecord.resId,
                    comment_type: commentRecord.data.comment_type,
                    supplier_number: commentRecord.data.supplier_number,
                    elapsed_time_seconds: commentRecord.data.elapsed_time_seconds,
                    sequence: commentRecord.data.sequence,
                    create_date: commentRecord.data.create_date.toUTC().toFormat("yyyy-MM-dd HH:mm:ss"),
                }
                if (commentRecord.data.comment_type == "user") {
                    this.state.comments["user"] = comment;
                } else {
                    this.state.comments[comment.supplier_number] = comment;
                }
            }
            const emptyComment = {
                id: 0,
                elapsed_time_seconds: this.props.record.data['current_elapsed_time_seconds'],
                sequence: 0,
                create_date: null,
            };

            // Nu User
            if (!this.state.comments["user"]) {
                this.state.comments["user"] = {
                    ...emptyComment,
                    comment_type: "user",
                    supplier_number: 0,
                };
            }
            // Supplier
            for (const supplier_number of this.supplierNumbers) {
                if (!this.state.comments[supplier_number]) {
                    this.state.comments[supplier_number] = {
                        ...emptyComment,
                        comment_type: "supplier",
                        supplier_number: supplier_number,
                    };
                }
                const event_line_id = this.props.record.data.selected_supplier_ids.records.find(
                    x => x.data.supplier_number == supplier_number
                );
                this.state.comments[supplier_number]["event_line_id"] = [event_line_id.resId, ""];
                this.state.comments[supplier_number]["event_line_vehicle_id"] = event_line_id.data.truck_id;
            }
            // Configure
            this.configureTrackingTimer();
        });

        onWillUnmount(() => {
            this.stopTrackingTimeTimer();
        });
    }
    configureTrackingTimer() {
        if (this.tracking_time) {
            const minElapsedSeconds = Math.min(
                ...Object.values(this.state.comments).map(x => x.elapsed_time_seconds)
            );
            if (minElapsedSeconds < this.tracking_time) {
                this.startTrackingTimeTimer();
            }
            const maxElapsedSeconds = Math.max(
                ...Object.values(this.state.comments).map(x => x.elapsed_time_seconds)
            );
            this.state.trackingTimeWarning = maxElapsedSeconds >= this.tracking_time;
            // console.log("comments", this.state.comments, maxElapsedSeconds);
        }
    }
    openCommentForm(ev, commentKey) {
        ev.preventDefault();
        ev.stopPropagation();
        const comment = this.state.comments[commentKey];

        const ike_uuid = this.props.record.context.ike_uuid;
        let context = {
            default_event_id: this.props.record.resId,
            default_stage_id: this.props.record.data.stage_id[0],
            default_comment_type: comment.comment_type,
            default_supplier_number: comment.supplier_number,
            default_sequence: comment.sequence + 1,
            default_previous_date: comment.previous_date || this.previous_date,
            default_event_line_id: comment.event_line_id ? comment.event_line_id[0] : null,
            ike_uuid: ike_uuid,
            // no_create: !this.state.trackingTimeWarning,
        }
        let tracking_time = this.tracking_time;

        this.dialog.add(FormViewDialog, {
            title: _t("Tracking Log"),
            resId: false,
            resModel: "ike.event.stage.comment",
            context: context,
            onRecordSaved: async (record) => {
                // console.log("onRecordSave", record);
                if (tracking_time) {
                    let lastRecord = record;
                    const recordsLen = record.data.stage_comment_ids.records.length;
                    if (recordsLen) {
                        lastRecord = record.data.stage_comment_ids.records[recordsLen - 1];
                    }
                    const lastComment = {
                        id: lastRecord.resId,
                        comment_type: comment.comment_type,
                        supplier_number: comment.supplier_number,
                        event_line_id: comment.event_line_id,
                        event_line_vehicle_id: comment.event_line_vehicle_id,
                        sequence: lastRecord.data.sequence,
                        elapsed_time_seconds: lastRecord.data.elapsed_time_seconds,
                        create_date: lastRecord.data.create_date.toUTC().toFormat("yyyy-MM-dd HH:mm:ss"),
                    };
                    this._updateComment(lastComment);
                }
            },
            onRecordDiscarded: () => {
                // console.log("onRecordDiscarded", this);
                if (tracking_time) {
                    this.orm.searchRead(
                        "ike.event.stage.comment",
                        [
                            ['id', '!=', comment.id],
                            ['event_id', '=', this.props.record.resId],
                            ['stage_id', '=', this.props.record.data.stage_id[0]],
                            ['comment_type', '=', comment.comment_type],
                            ['supplier_number', '=', comment.supplier_number],
                            ['sequence', '>', comment.sequence],
                        ],
                        [
                            'elapsed_time_seconds', 'sequence', 'create_date',
                        ],
                        {
                            order: 'sequence desc',
                            limit: 1,
                        },
                    ).then(result => {
                        if (result && result.length) {
                            const lastComment = {
                                ...result[0],
                                comment_type: comment.comment_type,
                                supplier_number: comment.supplier_number,
                                event_line_id: comment.event_line_id,
                                event_line_vehicle_id: comment.event_line_vehicle_id,
                            };
                            this._updateComment(lastComment);
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
    openCommentList(ev) {
        ev.preventDefault();
        ev.stopPropagation();
        this.action.doAction({
            name: _t("Comments"),
            type: "ir.actions.act_window",
            res_model: "ike.event.stage.comment",
            views: [
                [false, "list"]
            ],
            domain: [["event_id", "=", this.props.record.resId]],
            context: {
                create: false,
                edit: false,
                delete: false,
                duplicate: false,
                search_default_group_by_comment_type: true,
            },
            target: "new",
        });
    }
    _updateComment(lastComment) {
        if (lastComment.comment_type == "user") {
            this.state.comments["user"] = lastComment;
        } else {
            this.state.comments[lastComment.supplier_number] = lastComment;

        }
        this.configureTrackingTimer();
    }
    startTrackingTimeTimer() {
        this.stopTrackingTimeTimer()
        this.trackingTimeInterval = setInterval(() => {
            try {
                for (const key in this.state.comments) {
                    this.state.comments[key].elapsed_time_seconds += 1;
                }
                const minElapsedSeconds = Math.min(
                    ...Object.values(this.state.comments).map(x => x.elapsed_time_seconds)
                );
                if (minElapsedSeconds >= this.tracking_time) {
                    this.state.trackingTimeWarning = true;
                    this.stopTrackingTimeTimer();
                }
            } catch (err) {
                console.err("startTrackingTimeTimer", err);
            }
        }, MINUTE_SECONDS);
    }
    stopTrackingTimeTimer() {
        if (this.trackingTimeInterval) {
            clearInterval(this.trackingTimeInterval);
            this.trackingTimeInterval = null;
        }
    }
    prevent(ev) {
        ev.preventDefault();
        ev.stopPropagation();
    }
};

export const ikeStageTrackingComment = {
    component: IkeStageTrackingComment,
};

registry.category("fields").add("ike_stage_tracking_comment", ikeStageTrackingComment);
