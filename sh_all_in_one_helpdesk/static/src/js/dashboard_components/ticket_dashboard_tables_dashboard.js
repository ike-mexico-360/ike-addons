/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService, useBus } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";
import { Pager } from "@web/core/pager/pager";
const DEFAULT_LIMIT = 8;



export class TicketDashboardTablesView extends Component {
    static props = {
        data_dict: { type: Object, optional: true },
        table_data: { type: Object, optional: true },
        Currentdata: { type: Object, optional: true },
        updateTableData: { type: Function },
        stage_id: { type: Number, optional: true },
    };

    setup() {

        this.orm = useService("orm")
        this.action = useService("action");
        this.state = useState({
            table_data: this.props.table_data,
            pagerProps: {
                offset: 0,
                limit: DEFAULT_LIMIT,
                total: this.props.table_data.count_tickets,
            },
            CurrentData: this.props.Currentdata,

        });

        useBus(this.env.bus, 're_render_tables_with_filter', (ev) => this._reRenderTablesWithFilter(ev.detail));

    }

    async _reRenderTablesWithFilter(CurrentData) {
        var normalCurrentData;
        if (CurrentData.CurrentData) {
            normalCurrentData = Object.assign({}, CurrentData.CurrentData);
        } else {
            normalCurrentData = Object.assign({}, CurrentData);
        }
        
        const team_leader = normalCurrentData.teamLeader.id ?? false;
        const team = normalCurrentData.team.id ?? false;
        const assigned_user = normalCurrentData.assigned_user.id ?? false;
        const date_options_value = normalCurrentData.date_options_value ?? false;
        var start_date = normalCurrentData.start_date ?? false;
        if (start_date) {
            start_date = start_date.toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' });
        }

        var end_date = normalCurrentData.end_date ?? false;
        if (end_date) {
            end_date = end_date.toLocaleDateString('en-US', { year: 'numeric', month: '2-digit', day: '2-digit' });
        }

        const stage_id = this.props.stage_id
        var limit = this.state.pagerProps.limit
        var offset = this.state.pagerProps.offset

        const table_args = [team_leader, team, assigned_user, date_options_value, start_date, end_date, limit, offset, stage_id] // [team_leader, team, assign_user, filter_date, start_date, end_date,limit,offset,stage_id]        

        const getTicketData = await this.orm.call("ticket.dashboard", "get_ticket_table_data", table_args);

        this.state.table_data = getTicketData[0]
        this.state.pagerProps.total = getTicketData[0].count_tickets
        this.state.CurrentData = CurrentData

    }

    get getTableData() {
        return this.state.table_data
    }

    /**
     * @param {Object} param0
     * @param {number} param0.offset
     * @param {number} param0.limit
     */
    onUpdatePager({ offset, limit }) {
        this.state.pagerProps.offset = offset;
        this.state.pagerProps.limit = limit;
        this._reRenderTablesWithFilter(this.state.CurrentData);
    }

    async openTicket(ticket_id) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: _t('Helpdesk Tickets'),
            target: 'current',
            res_id: ticket_id,
            res_model: 'sh.helpdesk.ticket',
            views: [[false, 'form']],
        });
    }

    async action_send_whatsapp(ticket_id) {
        const action = await this.orm.call('sh.helpdesk.ticket', 'action_send_whatsapp', [ticket_id], {});
        this.action.doAction(action);

    }
}


TicketDashboardTablesView.template = "ticket_dashboard_tables.dashboard";

TicketDashboardTablesView.components = { Pager };


