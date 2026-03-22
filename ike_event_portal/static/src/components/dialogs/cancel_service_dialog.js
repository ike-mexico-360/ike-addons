/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class CancelServiceDialog extends Component {
    static template = "ike_event_portal.CancelServiceDialog";

    static props = {
        title: { type: String, optional: true },
        close: { type: Function },
        onConfirm: { type: Function },
    };

    static defaultProps = {
        title: "Cancelar Servicio",
    };

    setup() {
        this.orm = useService("orm");

        this.state = useState({
            reasonOption: '',
            reasonText: '',
            isSubmitting: false,
            isLoading: true,
        });

        this.cancelReasons = [];

        onWillStart(async () => {
            await this.loadCancelReasons();
        });
    }

    async loadCancelReasons() {
        try {
            const reasons = await this.orm.searchRead(
                'ike.event.cancellation.reason',
                [['show_supplier', '=', true], ['disabled', '=', false]],
                ['id', 'name'],
                { order: 'sequence' }
            );
            this.cancelReasons = reasons.map(r => ({
                value: r.id,
                label: r.name,
            }));
        } catch (err) {
            console.error("Error loading cancel reasons:", err);
            // Fallback to empty list
            this.cancelReasons = [];
        } finally {
            this.state.isLoading = false;
        }
    }

    get isValid() {
        if (!this.state.reasonOption) {
            return false;
        }
        return true;
    }

    onReasonChange(ev) {
        this.state.reasonOption = parseInt(ev.target.value, 10) || '';
    }

    onReasonTextChange(ev) {
        this.state.reasonText = ev.target.value;
    }

    async onConfirmClick() {
        if (!this.isValid) {
            return;
        }

        this.state.isSubmitting = true;
        try {
            await this.props.onConfirm({
                cancel_reason_id: this.state.reasonOption,
                reasonText: this.state.reasonText,
            });
            this.props.close();
        } catch (err) {
            console.error("Error confirming cancellation:", err);
            this.state.isSubmitting = false;
        }
    }

    onCancelClick() {
        this.props.close();
    }
}
