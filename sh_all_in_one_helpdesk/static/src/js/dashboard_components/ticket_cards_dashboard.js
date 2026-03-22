/** @odoo-module */

import { Component, onWillStart, useState } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { useService, useBus } from "@web/core/utils/hooks";

export class TicketCardsDashboardView extends Component {
    static props = {       
        data_dict: { type: Object, optional: true },
    };
    setup() {
        this.orm = useService("orm")
        this.action = useService("action");
        onWillStart(async () => await this.fetchHierarchy());
        this.state = useState({ data_dict: {} ,"color_dict": {}});
        useBus(this.env.bus, 'cards_dashboard', (ev) => this._fetchLunchInfos(ev.detail));
        useBus(this.env.bus, 're_render_cards_with_filter', (ev) => this._reRenderCardsWithFilter(ev.detail));

    }

    async fetchHierarchy() {
        this.state.data_dict = {}
        const args = [false, false, false, false, false, false]
        const TicketCardsData = await this.orm.call("ticket.dashboard", "get_ticket_counter_data", args);
        this.state.data_dict = TicketCardsData[0]
        this.state.color_dict = TicketCardsData[1]
    }

    async _reRenderCardsWithFilter(CurrentData) {

        const normalCurrentData = Object.assign({}, CurrentData.CurrentData);
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
        const cards_args = [team_leader, team, assigned_user, date_options_value, start_date, end_date] // [team_leader, team, assign_user, filter_date, start_date, end_date]
        const TicketCardsData = await this.orm.call("ticket.dashboard", "get_ticket_counter_data", cards_args);
        this.state.data_dict = TicketCardsData[0]
        this.state.color_dict = TicketCardsData[1]

    }

    get getTempValue() { 
        return this.state.data_dict 
    }

    _onClickCards(ev) {
        
        let resIdsString = (ev.target).closest('a').getAttribute('res_ids');
        
        if (resIdsString){
            let resIdsArray = resIdsString.split(',');
    
            let resIdsNumbers = resIdsArray.map(Number);
            this.action.doAction({
                type: 'ir.actions.act_window',
                name: _t('Helpdesk Tickets'),
                res_model: 'sh.helpdesk.ticket',
                views: [[false, 'list'], [false, 'kanban'], [false, 'form']],
                domain: [['id', 'in', resIdsNumbers]],
            });
        }
    }


}
TicketCardsDashboardView.template = "ticket_dashboard_cards.dashboard";
// TicketCardsDashboardView.props = {
//    //  ...standardActionServiceProps,
//     data_dict: Object,
// };