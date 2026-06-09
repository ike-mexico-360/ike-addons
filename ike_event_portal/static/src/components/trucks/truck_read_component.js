/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

export class TruckReadComponent extends Component {
    static template = "ike_event_portal.TruckReadComponent";
    static props = {
        truckId: { type: Number },
        onBack: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.user = user;
        this.state = useState({
            truck: null,
            isLoading: true,
            canEditDriver: false,
            showEditDriverModal: false,
            availableDrivers: [],
            isLoadingDrivers: false,
            selectedDriverId: '',
            isSaving: false,
        });

        onWillStart(async () => {
            await this.loadTruckDetail();
            await this.checkUserPermissions();
        });
    }

    showNotification({ message, type = 'info', sticky = true, title }) {
        this.notification.add(message, { type, sticky, title });
    }

    async loadTruckDetail() {
        if (!this.props.truckId) {
            this.showNotification({ title: _t("Missing truck"), message: _t("No Truck ID provided."), type: 'warning' });
            this.state.isLoading = false;
            return;
        }

        this.state.isLoading = true;
        try {
            const truckData = await rpc(`/fleet/vehicle/safe/${this.props.truckId}`);
            if (truckData.length) {
                this.state.truck = truckData[0];
            } else {
                this.showNotification({ title: _t("Truck not found"), message: _t("The requested truck could not be found."), type: 'warning' });
            }
        } catch (err) {
            this.showNotification({ title: _t("Error loading truck"), message: _t(err?.data?.message || err.message || "An error occurred while fetching truck details."), type: 'danger' });
        } finally {
            this.state.isLoading = false;
        }
    }

    async checkUserPermissions() {
        try {
            const result = await rpc('/provider/portal/trucks/can_edit_driver');
            this.state.canEditDriver = result.can_edit;
        } catch (err) {
            this.showNotification({ title: _t("Error checking permissions"), message: _t(err?.data?.message || err.message || "An error occurred while checking user permissions."), type: 'danger' });
            this.state.canEditDriver = false;
        }
    }

    async openEditDriverModal() {
        this.state.showEditDriverModal = true;

        // Set current driver as selected
        this.state.selectedDriverId = this.state.truck.driver_id ? this.state.truck.driver_id[0].toString() : '';

        // Load available drivers
        await this.loadAvailableDrivers();
    }

    closeEditDriverModal() {
        this.state.showEditDriverModal = false;
        this.state.availableDrivers = [];
        this.state.selectedDriverId = '';
    }

    async loadAvailableDrivers() {
        if (!this.state.truck.x_center_id) {
            this.state.availableDrivers = [];
            return;
        }

        this.state.isLoadingDrivers = true;
        try {
            const centerId = this.state.truck.x_center_id[0];
            const drivers = await rpc('/provider/portal/trucks/available_drivers', {
                center_of_attention_id: centerId
            });

            // Include current driver in the list if it exists
            if (this.state.truck.driver_id) {
                const currentDriver = {
                    id: this.state.truck.driver_id[0],
                    name: this.state.truck.driver_id[1]
                };
                // Check if current driver is not already in the list
                const driverExists = drivers.some(d => d.id === currentDriver.id);
                if (!driverExists) {
                    drivers.push(currentDriver);
                }
            }

            this.state.availableDrivers = drivers;
        } catch (err) {
            this.showNotification({ title: _t("Error loading drivers"), message: _t(err?.data?.message || err.message || "An error occurred while loading the available drivers."), type: 'danger' });
            this.state.availableDrivers = [];
        } finally {
            this.state.isLoadingDrivers = false;
        }
    }

    async saveDriver() {
        this.state.isSaving = true;

        try {
            const driverId = this.state.selectedDriverId ? parseInt(this.state.selectedDriverId) : false;

            const result = await rpc('/provider/portal/trucks/update_driver', {
                truck_id: this.props.truckId,
                driver_id: driverId
            });

            if (!result.success) {
                this.showNotification({ title: _t("Error saving driver"), message: _t(result.error || "An error occurred while saving the driver."), type: 'danger' });
                return;
            }

            this.showNotification({ title: _t("Driver updated"), message: _t(result.message || "The driver has been updated successfully."), type: 'success' });
            await this.loadTruckDetail();
            this.closeEditDriverModal();
        } catch (err) {
            this.showNotification({ title: _t("Error saving driver"), message: _t(err?.data?.message || err.message || "An error occurred while saving the driver."), type: 'danger' });
        } finally {
            this.state.isSaving = false;
        }
    }
}

registry.category("components").add("ike_event_portal.TruckReadComponent", TruckReadComponent);