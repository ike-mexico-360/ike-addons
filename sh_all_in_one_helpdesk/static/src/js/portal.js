/** @odoo-module **/
import { _t } from "@web/core/l10n/translation";
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.SHCreateTicketPopup = publicWidget.Widget.extend({
    selector: '#createticketModal , .sh_create_btn',

    events: {
        'change #portal_file': '_onChangePortalFile',
        'click #partner_id': '_onClickPartner',
        'click #portal_category': '_onClickPortalCategory',
        'click #portal_team': '_onClickPortalTeam',
        'click #new_request':'_onClickNewRequest',
    },

    init() {
        this._super(...arguments);
        // this.rpc = this.bindService("rpc");
    },

    /**
    * @override
    */
    start: function () {
        var def = this._super.apply(this, arguments);
        var self = this
        // $(".sh_custom_user_ids").select2();
    },

    _onChangePortalFile: function (ev) {
        for (var x in ev.currentTarget.files) {
            if (ev.currentTarget.files[x].size / 1024 > $('#sh_file_size').val()) {
                alert(ev.currentTarget.files[x].name + " exceeds the " + String($('#sh_file_size').val()) + "KB file size limit");
                $("#portal_file").val("");
            }
        }
    },

    _onClickNewRequest: function (ev) {
        $("#createticketModal").modal("show");
    },

    _onClickPortalCategory: function (ev) {
        $.ajax({
            url: "/portal-subcategory-data",
            data: { category_id: $("#portal_category").val() },
            type: "post",
            cache: false,
            success: function (result) {
                var datas = JSON.parse(result);
                $("#portal_subcategory > option").remove();
                $("#portal_subcategory").append('<option value="' + "sub_category" + '">' + "Select Sub Category" + "</option>");
                $.each(datas.sub_categories, function(index, data) {
                    $("#portal_subcategory").append('<option value="' + data.id + '">' + data.name + "</option>");
                });
            },
        });
    },

    _onClickPartner: function (ev) {
        if ($("#partner_id").val() != "") {
            $.ajax({
                url: "/selected-partner-data",
                data: { partner_id: $("#partner_id").val() },
                type: "post",
                cache: false,
                success: function (result) {
                    var datas = JSON.parse(result);
                    $("#portal_contact_name").val(datas.name);
                    $("#portal_email").val(datas.email);
                },
            });
        } else {
            $("#portal_contact_name").val("");
            $("#portal_email").val("");
        }
    },
});
