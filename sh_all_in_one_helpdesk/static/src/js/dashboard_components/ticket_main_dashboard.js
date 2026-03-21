/** @odoo-module */
/** A magical journey into the world of ticket dashboards.*/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { TicketCardsDashboardView } from "@sh_all_in_one_helpdesk/js/dashboard_components/ticket_cards_dashboard";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { _t } from "@web/core/l10n/translation";
import { TicketDashboardTablesView } from "@sh_all_in_one_helpdesk/js/dashboard_components/ticket_dashboard_tables_dashboard";
import { ListRenderer } from "@web/views/list/list_renderer";
import { session } from '@web/session';

// Let the dashboard extravaganza begin!
export class TicketDashboardView extends Component {

    // Initializing state and setting the stage for some serious ticket magic.
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.user = user
        this.state = useState({
            infos: {},
            teamLeader: { id: false },
            selected_team_leader: false,
            team: { id: false },
            selected_assigned_user: false,
            assigned_user: { id: false },
            activeActions: {},
            selected_team: '',
            stage_id: 0,
            table_data: []
        });


        // Preparing for the ride by fetching essential data.
        onWillStart(async () => {
            
            const getTeam = await this.orm.call("ticket.dashboard", "get_team", []);
            this.getTeam = getTeam;

            const getAllUsers = await this.orm.call("ticket.dashboard", "get_users", []);
            this.getAllUsers = getAllUsers;

            const stage_id = false;
            const args = [false, false, false, false, false, false, 0, 0, stage_id];
            const getTicketData = await this.orm.call("ticket.dashboard", "get_ticket_table_data", args);
            this.state.table_data = getTicketData;
            this.is_helpdesk_manager = await this.user.hasGroup("sh_all_in_one_helpdesk.helpdesk_group_manager");
            this.is_helpdesk_team_leader = await this.user.hasGroup("sh_all_in_one_helpdesk.helpdesk_group_team_leader");
            this.is_helpdesk_support_user = await this.user.hasGroup("sh_all_in_one_helpdesk.helpdesk_group_user");

        });   
    }

    // Triggering the ticket bus - "Please update state, we've got tickets to show!"
    _triggerBusToUpdateState() {
        this.env.bus.trigger('re_render_cards_with_filter', { CurrentData: this.state });
        this.env.bus.trigger('re_render_tables_with_filter', { CurrentData: this.state });
    }

    // Updating the start date - because even tickets have a beginning.
    async UpdateStartDates(date = false) {
        if (date) {
            const start_date = new Date(date.c.year, date.c.month - 1, date.c.day);
            this.state.start_date = start_date;
            this._triggerBusToUpdateState();
        } else {
            this.state.start_date = false;
            this._triggerBusToUpdateState();
        }
    }

    // Updating the end date - because even tickets need closure.
    async UpdateEndDates(date = false) {
        if (date) {
            const end_date = new Date(date.c.year, date.c.month - 1, date.c.day);
            this.state.end_date = end_date;
            this._triggerBusToUpdateState();
        } else {
            this.state.end_date = false;
            this._triggerBusToUpdateState();
        }
    }

    // Handling filter changes - where even filters have a dramatic impact.
    _onchangefilter(ev) {
        // The filter dance - when options change, the magic begins!
        var date_options_value = false;
        if (ev.target.value != 'all' && ev.target.value != 'custom') {
            date_options_value = ev.target.value;
            this.state.date_options_value = date_options_value;
            this.state.select_date_type = date_options_value;
            this._triggerBusToUpdateState();
        }

        // When all is selected, the world (of tickets) is your oyster!
        if (ev.target.value == 'all') {
            var date_options_value = false;
            this.state.date_options_value = date_options_value;
            this.state.select_date_type = date_options_value;
            this._triggerBusToUpdateState();
        }

        // Custom mode - because sometimes tickets need a bespoke experience.
        if (ev.target.value == 'custom') {
            this.state.select_date_type = false;
            this.state.date_options_value = 'custom';
            this._triggerBusToUpdateState();
        }
    }

    // Properties for the majestic Team Leader autocomplete.
    get many2XAutocompletePropsTeamLeader() {
        return {
            resModel: "res.users",
            value: this.state.selected_team_leader ? this.state.selected_team_leader : '',
            fieldString: _t("Select a Team Leader"),
            getDomain: this.getDomainTeamLeader.bind(this),
            activeActions: {},
            update: this.updateTeamLeader.bind(this),
            placeholder: _t("Select a Team Leader..."),
            quickCreate: null,
        };
    }

    // The domain where Team Leaders roam free (but not too freely).
    getDomainTeamLeader() {
        return [['share', '!=', true]];
    }

    // Updating the Team Leader - because every team needs a guiding light.
    updateTeamLeader(selectedMenus) {
        if (selectedMenus) {
            const userWithId = this.getAllUsers.find(user => user.id === selectedMenus[0].id);
            this.state.teamLeader = selectedMenus[0];
            this.state.selected_team_leader = userWithId.name;
            selectedMenus[0].id;
            this._triggerBusToUpdateState();
        } else {
            this.state.teamLeader = { id: false };
            this.state.selected_team_leader = false;
            this._triggerBusToUpdateState();
        }
    }

    // Properties for the epic Teams autocomplete.
    get many2XAutocompletePropsTeams() {
        return {
            resModel: "sh.helpdesk.team",
            value: this.state.selected_team ? this.state.selected_team : '',
            fieldString: _t("Select a Team..."),
            getDomain: this.getDomainTeam.bind(this),
            update: this.updateTeam.bind(this),
            placeholder: _t("Select a Team..."),
            activeActions: { 'key': 'value' },
            quickCreate: null,
        };
    }

    // The domain where Teams gather, ready to embark on their ticket adventures.
    getDomainTeam() {
        return [['id', '!=', 0]];
    }

    // Updating the Team - because teamwork makes the ticket dream work.
    updateTeam(selectedMenus) {
        if (selectedMenus) {
            const userWithId = this.getTeam.find(team => team.id === selectedMenus[0].id);
            this.state.team = selectedMenus[0];
            this.state.selected_team = userWithId.name;
            this._triggerBusToUpdateState();
        } else {
            this.state.team = { id: false };
            this.state.selected_team = false;
            this._triggerBusToUpdateState();
        }
    }

    // Properties for the valiant Assigned User autocomplete.
    get many2XAutocompletePropsAssignedUser() {
        return {
            resModel: "res.users",
            value: this.state.selected_assigned_user ? this.state.selected_assigned_user : '',
            fieldString: _t("Select an Assigned User..."),
            getDomain: this.getDomainAssignedUser.bind(this),
            update: this.updateAssignedUser.bind(this),
            placeholder: _t("Select an Assigned User..."),
            activeActions: {},
            quickCreate: null,
        };
    }

    // The domain where Assigned Users await their ticket destiny.
    getDomainAssignedUser() {
        return [['share', '!=', true]];
    }

    // Updating the Assigned User - because every ticket needs a guardian.
    updateAssignedUser(selectedMenus) {
        if (selectedMenus) {
            const userWithId = this.getAllUsers.find(team => team.id === selectedMenus[0].id);
            this.state.assigned_user = selectedMenus[0];
            this.state.selected_assigned_user = userWithId.name;
            this._triggerBusToUpdateState();
        } else {
            this.state.assigned_user = { id: false };
            this.state.selected_assigned_user = false;
            this._triggerBusToUpdateState();
        }
    }

    // A grand update for the ticket table - because tables deserve love too.
    updateTableData = (newData) => {
        this.state.table_data = newData;
    };
}

// The grand template for the Ticket Dashboard - where tickets come alive!
TicketDashboardView.template = "ticket_dashboard.dashboard";

// Components that make this Ticket Dashboard a star-studded event.
TicketDashboardView.components = {
    TicketDashboardTablesView,
    TicketCardsDashboardView,
    Many2XAutocomplete,
    ListRenderer,
    DateTimeInput
};

// Props that ensure this dashboard is action-packed!
TicketDashboardView.props = {
    ...standardActionServiceProps
};

// Adding this masterpiece to the action category - because it's a ticket action like no other.
registry.category("actions").add("action_ticket_dashboard_dashboard", TicketDashboardView, { force: true });