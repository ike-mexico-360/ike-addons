/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";


export class PurchaseOrderDispute extends Component {
    static template = "ike_event_purchase.PurchaseOrderDispute"

    static props = {
        order_id: { type: Number, optional: false },
        action: { type: String, optional: false },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            sending_request: false,
            order_data: null,
            show_approved_banner: false,
            show_declined_banner: false,
        });

        // Cargar datos de la orden al iniciar el componente
        onWillStart(async () => {
            await this._loadOrderData();
            await this._sendDisputeActionRequest();
        });
    }

    async _loadOrderData() {
        this.state.loading = true;
        try {
            const order_data = await this.orm.webSearchRead(
                'purchase.order',
                [
                    ['id', '=', this.props.order_id]
                ],
                {
                    specification: {
                        id: {},
                        name: {},
                        state: {},
                        x_dispute_state: {},
                        x_dispute_approved: {},
                    }
                }
            );
            this.state.order_data = order_data.records[0] || null;
        } catch (e) {
            this.notification.add(_t("Error loading order data: ") + e.message, {
                type: "danger", sticky: true
            });
        } finally {
            this.state.loading = false;
        }
    }

    async _sendDisputeActionRequest() {
        this.state.sending_request = true;
        const action = this.props.action;
        if (action === 'accept') {
            try {
                await this.orm.call('purchase.order', 'x_action_approve_dispute', [this.props.order_id]);
                this.state.show_approved_banner = true;
                this.notification.add(_t("Dispute approved"), { type: "success" });
                this.closeWindow();
            } catch (e) {
                const errorMsg = e?.data?.message || e?.message || _t("Unknown error");
                this.notification.add(_t("Error at approve dispute: ") + errorMsg, {
                    type: "danger", sticky: true
                });
                console.log(e);
            } finally {
                this.state.sending_request = false;
            }
        } else if (action === 'decline') {
            try {
                await this.orm.call('purchase.order', 'x_action_reject_dispute', [this.props.order_id]);
                this.state.show_declined_banner = true;
                this.notification.add(_t("Dispute declined"), { type: "warning" });
                this.closeWindow();
            } catch (e) {
                this.notification.add(_t("Error at decline dispute: ") + e.message, {
                    type: "danger", sticky: true
                });
            } finally {
                this.state.sending_request = false;
            }
        } else {
            this.state.sending_request = false;
            this.notification.add(_t("Invalid dispute action: ") + action, { type: "danger" });
        }
    }

    closeWindow() {
        setTimeout(() => window.close(), 4000);
    }
}

registry.category("public_components").add("ike_event_purchase.purchase_order_dispute", PurchaseOrderDispute);
