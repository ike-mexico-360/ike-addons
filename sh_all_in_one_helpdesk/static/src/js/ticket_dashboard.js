odoo.define('sh_all_in_one_helpdesk.dashboard', function (require) {
    "use strict";
    var AbstractAction = require('web.AbstractAction');
    var ajax = require('web.ajax');
    var core = require('web.core');
    var _t = core._t;
    var rpc = require('web.rpc');
    var session = require('web.session');
    var QWeb = core.qweb;
    var TicketDashboardView = AbstractAction.extend({
        events: {
            'change #team_leader': 'action_get_team',
            'change #team': 'action_get_team_members',
            'change #days_filter': 'render_ticket_data',
            'change #start_date': 'render_ticket_data',
            'change #end_date': 'render_ticket_data',
            'click .mark-whatsapp': 'action_whatsapp',
            'click .sh_tile_click': 'action_open_tickets',
            'change #ticket_partner_id': 'action_partner_change',
            'click #send': 'action_send_whatsapp',
        },
        init: function (parent, context) {
            this._super(parent, context);
            var self = this;
            if (context.tag == 'ticket_dashboard.dashboard') {

                self._rpc({
                    model: 'ticket.dashboard',
                    method: 'get_user_group',
                })
                    .then(function (messagesData) {
                        var datas = JSON.parse(messagesData);
                        if (datas.user == "1") {
                            $("#leader_div").addClass("o_hidden");
                            $("#team_div").addClass("o_hidden");
                            $("#assign_user_div").addClass("o_hidden");
                        } else if (datas.leader == "1") {
                            $("#leader_div").addClass("o_hidden");
                            $("#team_div").removeClass("o_hidden");
                            $("#assign_user_div").removeClass("o_hidden");
                        } else if (datas.manager == "1") {
                            $("#leader_div").removeClass("o_hidden");
                            $("#team_div").removeClass("o_hidden");
                            $("#assign_user_div").removeClass("o_hidden");
                        }
                    });
                self._rpc({
                    model: 'ticket.dashboard',
                    method: 'get_team_leader',
                })
                    .then(function (messagesData) {
                        _.each(messagesData, function (data) {
                            $("#team_leader").append('<option data-id="' + data.id + '" value="' + data.id + '">' + data.name + '</option>');
                        });
                        self.render_ticket_data();
                    });
            }
        },
        render_ticket_data: function (event) {
            var self = this;
            if ($('#days_filter').val() == 'custom') {
                $('#start_date').removeClass('o_hidden');
                $('#end_date').removeClass('o_hidden');
            } else {
                $('#start_date').addClass('o_hidden');
                $('#end_date').addClass('o_hidden');
                $('#start_date').val('');
                $('#end_date').val('');
            }
            self._rpc({
                model: 'ticket.dashboard',
                method: 'get_ticket_counter_data',
                args: [$('#team_leader').val(), $('#team').val(), $('#assign_user').val(), $('#days_filter').val(), $('#start_date').val(), $('#end_date').val()],
            })
                .then(function (messagesData) {
                    $("#js_ticket_count_div").replaceWith(messagesData);

                });
            self._rpc({
                model: 'ticket.dashboard',
                method: 'get_ticket_table_data',
                args: [$('#team_leader').val(), $('#team').val(), $('#assign_user').val(), $('#days_filter').val(), $('#start_date').val(), $('#end_date').val()],
            })
                .then(function (messagesData) {
                    $("#js_ticket_tbl_div").replaceWith(messagesData);

                });
        },
        action_get_team: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();
            $('#team > option').remove();
            $("#team").append('<option value="0" selected="True">Team</option>');
            self._rpc({
                model: 'ticket.dashboard',
                method: 'get_team',
                args: [$('#team_leader').val()],
            })
                .then(function (messagesData) {
                    _.each(messagesData, function (data) {
                        $("#team").append('<option data-id="' + data.id + '" value="' + data.id + '">' + data.name + '</option>');
                    });
                    self.render_ticket_data();
                });
        },
        action_get_team_members: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();
            $('#assign_user > option').remove();
            $("#assign_user").append('<option value="0" selected="True">Assign User</option>');
            self._rpc({
                model: 'ticket.dashboard',
                method: 'get_team_members',
                args: [$('#team').val()],
            })
                .then(function (messagesData) {
                    _.each(messagesData, function (data) {
                        $("#assign_user").append('<option data-id="' + data.id + '" value="' + data.id + '">' + data.name + '</option>');
                    });
                    self.render_ticket_data();
                });
        },
        action_whatsapp: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();
            var $el = $(event.target).parents("tr").find("#partner_id").attr("value");
            var $mobile = $(event.target).parents("tr").find("#partner_id").attr("data-mobile");
            var partner_id = parseInt($el);
            $(".whatsapp_modal").modal("show");
            $("#ticket_partner_id").val(partner_id);
            $("#partner_mobile_no").val($mobile);
        },
        action_send_whatsapp: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();
            self._rpc({
                model: 'ticket.dashboard',
                method: 'send_by_whatsapp',
                args: [$('#ticket_partner_id').val(), $("#partner_mobile_no").val(), $('#whatsapp_message').val()],
            })
                .then(function (messagesData) {
                    var datas = JSON.parse(messagesData);
                    if (datas.msg) {
                        alert(datas.msg);
                    } else {
                        if (datas.url) {
                            window.open(datas.url, '_blank');
                        }
                    }
                });
        },
        action_partner_change: function (event) {
            var self = this;
            event.stopPropagation();
            event.preventDefault();
            self._rpc({
                model: 'ticket.dashboard',
                method: 'get_mobile_no',
                args: [$('#ticket_partner_id').val()],
            })
                .then(function (messagesData) {
                    var datas = JSON.parse(messagesData);
                    if (datas) {
                        $("#partner_mobile_no").val(datas.mobile);
                    } else {
                        $("#partner_mobile_no").val('');
                    }
                });
        },

        action_open_tickets: function (event) {
            var self = this;
            var $el = $(event.currentTarget).attr('data-res_ids') || [];
            var list_value = JSON.parse("[" + $el + "]");
            var comma_string = list_value.toString();
            var all_tickets = comma_string.split(",").map(Number);
            this._rpc({
                model: 'ir.model.data',
                method: 'xmlid_to_res_model_res_id',
                args: ["sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view"],
            })
                .then(function (data) {
                    self.do_action({
                        name: _t("Tickets"),
                        type: 'ir.actions.act_window',
                        res_model: 'sh.helpdesk.ticket',
                        view_mode: 'kanban,list,form',
                        views: [
                            [false, 'kanban'],
                            [false, 'list'],
                            [data[1], 'form']
                        ],
                        domain: [
                            ['id', 'in', all_tickets],
                            '|', ['active', '=', false],
                            ['active', '=', true],
                        ],
                        target: 'current'
                    }, {

                    })
                })
        },

        // willStart: function() {
        //     return $.when(ajax.loadLibs(this), this._super());

        // },
        start: function () {
            var self = this;
            self.render();
            return this._super();
        },

        render: function () {
            var self = this;
            var ticket_dashboard = QWeb.render('ticket_dashboard.dashboard', {
                widget: self,
            });
            $(ticket_dashboard).prependTo(self.$el);
            return ticket_dashboard
        },
        reload: function () {
            location.reload();

        },

    });
    core.action_registry.add('ticket_dashboard.dashboard', TicketDashboardView);
    return TicketDashboardView

});