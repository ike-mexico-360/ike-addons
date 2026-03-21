/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, markup } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Dialog } from "@web/core/dialog/dialog";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

// --- TABLE COMPONENT (DIALOG) ---
export class BinnacleDialog extends Component {
    static template = "ike_event_binnacle.BinnacleDialogTable";
    static components = { Dialog };

    // Fix: Added static props description to avoid console warning
    static props = {
        title: { type: String },
        records: { type: Array },
        close: { type: Function }, // Automatically passed by dialogService
    };

    setup() {
        this.processedRecords = this.props.records || [];
    }
}

// --- BUTTON COMPONENT (WIDGET) ---
export class IkeBinnacleButtonWidget extends Component {
    static template = "ike_event_binnacle.IkeBinnacleButton";
    static props = { ...standardWidgetProps };

    setup() {
        this.dialogService = useService("dialog");
        this.orm = useService("orm");
        this.user = user;
    }

    async onClick() {
        const resId = this.props.record.resId;
        const rawLang = this.user.lang || 'es_MX';
        const userLang = rawLang.replace('-', '_');

        // Optimized webSearchRead: One single call to fetch everything
        const { records: messages } = await this.orm.webSearchRead(
            "mail.message",
            [
                ["event_binnacle_id", "!=", false],
                ["model", "=", "ike.event"],
                ["res_id", "=", resId]
            ],
            {
                specification: {
                    id: {},
                    create_date: {},
                    body: {},
                    message_type: {},
                    author_id: { fields: { display_name: {} } },
                    event_binnacle_id: {
                        fields: {
                            binnacle_category_id: {
                                fields: {
                                    name: {},
                                    parent_id: {}
                                }
                            }
                        }
                    }
                },
                order: "id desc",
                context: { lang: userLang }
            }
        );

        if (!messages.length) {
            this.dialogService.add(BinnacleDialog, {
                title: _t("Event Binnacle"),
                records: []
            });
            return;
        }

        const dataForDialog = messages.map(msg => {
            const binnacle = msg.event_binnacle_id;
            const category = binnacle?.binnacle_category_id;

            let date_time = "";
            if (msg.create_date) {
                const localDate = deserializeDateTime(msg.create_date);
                date_time = formatDateTime(localDate, { format: "dd/MM/yyyy HH:mm:ss" });
            }

            return {
                id: msg.id,
                date_time: date_time,
                category: category?.name || "",
                author: msg.author_id?.display_name || "",
                comments: markup(msg.body || ""),
                is_highlight: !category?.parent_id && msg.message_type !== 'comment',
            };
        });

        this.dialogService.add(BinnacleDialog, {
            title: _t("Event Binnacle"),
            records: dataForDialog,
        });
    }
}

registry.category("view_widgets").add("ike_binnacle_button", {
    component: IkeBinnacleButtonWidget,
});