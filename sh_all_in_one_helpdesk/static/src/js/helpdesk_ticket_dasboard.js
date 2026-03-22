odoo.define('sh_all_in_one_helpdesk.sh_helpdesk_ticket_dasboard', function(require) {
    var ajax = require('web.ajax');
    var core = require('web.core');
    var rpc = require('web.rpc');

    var qweb = core.qweb;
    var _t = core._t;
    var KanbanRenderer = require("web.KanbanRenderer");
    KanbanRenderer.include({
        events: _.extend({}, KanbanRenderer.prototype.events || {}, {
            "click .sh_tile_click": "action_all_tickets",
        }),
        action_all_tickets: function(event) {
            event.stopPropagation();
            event.preventDefault();
            var self = this;
            var $el = $(event.currentTarget).attr("data-res_ids");
            if ($el == undefined) {
                this._rpc({
                    model: "ir.model.data",
                    method: "xmlid_to_res_model_res_id",
                    args: ["sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view"],
                }).then(function(data) {
                    self.do_action({
                        name: _t("Tickets"),
                        type: "ir.actions.act_window",
                        res_model: "sh.helpdesk.ticket",
                        view_mode: "kanban,list,form",
                        views: [
                            [false, "kanban"],
                            [false, "list"],
                            [data[1], "form"],
                        ],
                        domain: [
                            ["id", "in", []]
                        ],
                        target: "current",
                    }, );
                });
            } else {
                var list_value = JSON.parse($el);
                this._rpc({
                    model: "ir.model.data",
                    method: "xmlid_to_res_model_res_id",
                    args: ["sh_all_in_one_helpdesk.sh_helpdesk_ticket_form_view"],
                }).then(function(data) {
                    self.do_action({
                        name: _t("Tickets"),
                        type: "ir.actions.act_window",
                        res_model: "sh.helpdesk.ticket",
                        view_mode: "kanban,list,form",
                        views: [
                            [false, "kanban"],
                            [false, "list"],
                            [data[1], "form"],
                        ],
                        domain: [
                            ["id", "in", list_value]
                        ],
                        target: "current",
                    }, );
                });
            }
        },
    });
});