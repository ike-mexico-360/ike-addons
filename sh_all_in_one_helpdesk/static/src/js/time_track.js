/** @odoo-module */

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

function formatDuration(duration) {
    const seconds = Math.floor(duration / 1000);
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const remainingSeconds = seconds % 60;

    const formattedHours = String(hours).padStart(2, '0');
    const formattedMinutes = String(minutes).padStart(2, '0');
    const formattedSeconds = String(remainingSeconds).padStart(2, '0');

    return formattedHours + ":" + formattedMinutes + ":" + formattedSeconds;
}

class ChangeLine extends Component { }
ChangeLine.template = "account.ResequenceChangeLine";
ChangeLine.props = ["changeLine", "ordering"];

class TimeCounter extends Component {

    setup() {
        this.orm = useService('orm');
        this.state = useState({
            duration:
                this.props.value !== undefined ? this.props.value : this.props.record.data.duration,
        });
        // const userService = useService("user");
        this.actionService = useService("action");

        var self = this;
        let sh_id;
        // if ($.isNumeric((this.props.record.data.id))) {
        //     sh_id = this.props.record.data.id
        // } else if (this.props.record.resId) {
        //     sh_id = this.props.record.resId
        // }

        if (typeof this.props.record.data.id === 'number' && !isNaN(this.props.record.data.id))  {
            sh_id = this.props.record.data.id
        } else if (this.props.record.resId) {
            sh_id = this.props.record.resId
        }

        onWillStart(async () => {
            var self = this;
            let sh_id;
            // if ($.isNumeric((this.props.record.data.id))) {
            //     sh_id = this.props.record.data.id
            // } else if (this.props.record.resId) {
            //     sh_id = this.props.record.resId
            // }
            if (typeof this.props.record.data.id === 'number' && !isNaN(this.props.record.data.id)) {
                sh_id = this.props.record.data.id
            } else if (this.props.record.resId) {
                sh_id = this.props.record.resId
            }
            const result = await this.orm.call('sh.helpdesk.ticket', 'get_duration', [sh_id]);
            this.state.duration += result;
            if (this.props.record.data.start_time) {
                this._runTimer();
            }
         
        });

    }

    get sh_duration() {
        if (this.state.duration) {
            return formatDuration(this.state.duration);
            
        }
        else {
            return 0;
        }
    }

    _runTimer() {
        this.timer = setTimeout(() => {
            if (this.props.record.data.start_time) {
                this.state.duration += 1000;
                this._runTimer();
            }
        }, 1000);
    }
    
}
TimeCounter.template = "web.TaskTimeCounter";
TimeCounter.components = { ChangeLine };

registry.category("fields").add("task_time_counter", {
    component: TimeCounter,
});


