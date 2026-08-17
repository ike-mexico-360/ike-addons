import { CalendarController } from "@web/views/calendar/calendar_controller";
import { CalendarModel } from '@web/views/calendar/calendar_model';
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(CalendarModel.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        if (!this.state) {
            this.state = {};
        }
        
        if (!this.state.scale) {
            this.state.scale = 'week';
        }
        if (typeof this.state.appointee_id === 'undefined') {
            this.state.appointee_id = ''; // Default to no appointee selected
        }
    },

    async load(params = {}) {
        const appointee_id = params.appointee_id || this.state.appointee_id;
        this.state.appointee_id = appointee_id;  // Update appointee_id in the state
        this.meta.AppointeeData = await this.fetchAppointeeData(appointee_id);
        return super.load(...arguments);
    },
    
    //here overriding core method to display only those records which belong to the selected appointee
    async fetchRecords(data){
        if (this.meta.resModel != 'appointment'){
            return super.fetchRecords(data);
        }
        var records = await super.fetchRecords(data)
        var result = []
        if (this.state.appointee_id && this.state.appointee_id > -1)
        {
            records.forEach(record => {
                if (record.appoint_person_id[0] == this.state.appointee_id)
                {
                    result.push(record)
                }
            });
            return result
        }
        return records
    },

    async fetchAppointeeData(appointee_id) {
        if (appointee_id == -1){
            appointee_id = '';
        }
        return this.orm.call('appointment', 'fetch_appointee_data', [,appointee_id], {});
    },

});

patch(CalendarController.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.currentAppointeeId = -1;
        this.wkmodel = this.props.resModel;
        this.bookAnAppointment = this.bookAnAppointment.bind(this)
        this.onAppointeeChange = this.onAppointeeChange.bind(this);
    },

    wkGetModel() {
        return this.props.resModel === 'appointment';
    },

    bookAnAppointment(){
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: 'appointment',
            name: 'Book An Appointment',
            views: [[false, 'form']],
            target: 'new',
        });
    },

    onAppointeeChange(ev) {
        const appointeeId = parseInt(ev.target.value, 10);
        if (appointeeId === -1) {
            this.selectedAppointeeId = -1;  // for all appointees
        } else {
            this.selectedAppointeeId = appointeeId;
        }
        this.model.load({ appointee_id: this.selectedAppointeeId });
    },

    getListViewonClick(ev) {
        let domain = [];
        if (this.selectedAppointeeId !== -1 && this.selectedAppointeeId !== undefined && this.selectedAppointeeId !== null) {
            domain.push(['appoint_person_id', '=', this.selectedAppointeeId]);
        }
       
        if (ev.target.classList.contains('new_appointment')) {
            let newAppointmentDomain = [
                ['appoint_state', '=', 'new']
            ];
            const finalDomain = [...newAppointmentDomain, ...domain];
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'New Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: finalDomain,
            });
        }
        else if (ev.target.classList.contains('pending_appointment')) {
            var pendingAppointmentDomain = [
                ['appoint_state', '=', 'pending']
            ];
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'Pending Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: pendingAppointmentDomain.concat(domain),
            });
        }
        else if (ev.target.classList.contains('approved_appointment')) {
            var approvedAppointmentDomain = [
                ['appoint_state', '=', 'approved']
            ];
            
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'Approved Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: approvedAppointmentDomain.concat(domain),
            });
        }
        else if (ev.target.classList.contains('done_appointment')) {
            var doneAppointmentDomain = [
                ['appoint_state', '=', 'done']
            ];
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'Done Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: doneAppointmentDomain.concat(domain),
            });
        }
        else if (ev.target.classList.contains('cancelled_appointment')) {
            var cancelledAppointmentDomain = [
                ['appoint_state', '=', 'rejected']
            ];
            this.actionService.doAction({
                type: "ir.actions.act_window",
                res_model: 'appointment',
                name: 'Cancelled Appointments',
                views: [[false, 'list'], [false, 'form']],
                domain: cancelledAppointmentDomain.concat(domain),
            });
        }
    },
});
