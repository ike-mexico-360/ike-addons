/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class SelectVehicleDialog extends Component {
    static template = "ike_event_portal.SelectVehicleDialog";

    static props = {
        title: { type: String, optional: true },
        close: { type: Function },
        eventSupplierId: { type: Number },
        currentTruckId: { type: Number, optional: true },
        onConfirm: { type: Function },
    };

    static defaultProps = {
        title: _t("Select Service Vehicle"),
        currentTruckId: null,
    };

    translate(str) { return _t(str); }

    setup() {
        this.orm = useService("orm");

        this.state = useState({
            vehicles: [],
            selectedTruckId: null,
            isLoading: true,
            isSubmitting: false,
        });

        onWillStart(async () => {
            await this.loadVehicles();
        });
    }

    async loadVehicles() {
        try {
            const vehicles = await this.orm.call(
                'ike.event.supplier.public',
                'get_selectable_vehicles',
                [this.props.eventSupplierId]
            );
            this.state.vehicles = vehicles || [];
            const current = this.state.vehicles.find(v => v.id === this.props.currentTruckId);
            this.state.selectedTruckId = current ? current.id : (this.state.vehicles[0]?.id ?? null);
        } catch (err) {
            console.error("Error loading selectable vehicles:", err);
            this.state.vehicles = [];
            this.state.selectedTruckId = null;
        } finally {
            this.state.isLoading = false;
        }
    }

    get isValid() {
        return !!this.state.selectedTruckId;
    }

    onVehicleChange(ev) {
        this.state.selectedTruckId = parseInt(ev.target.value, 10) || null;
    }

    async onConfirmClick() {
        if (!this.isValid) {
            return;
        }

        this.state.isSubmitting = true;
        try {
            await this.props.onConfirm(this.state.selectedTruckId);
            this.props.close();
        } catch (err) {
            console.error("Error confirming vehicle selection:", err);
            this.state.isSubmitting = false;
        }
    }

    onCancelClick() {
        this.props.close();
    }
}
