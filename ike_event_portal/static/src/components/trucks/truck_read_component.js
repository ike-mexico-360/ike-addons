/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";

export class TruckReadComponent extends Component {
    static template = "ike_event_portal.TruckReadComponent";
    static props = {
        truckId: { type: Number },
        onBack: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.user = user;
        this.state = useState({
            truck: null,
            isLoading: true,
            error: null,
            canEditDriver: false,
            showEditDriverModal: false,
            availableDrivers: [],
            isLoadingDrivers: false,
            selectedDriverId: '',
            isSaving: false,
            saveError: null,
        });

        onWillStart(async () => {
            await this.loadTruckDetail();
            await this.checkUserPermissions();
        });
    }

    async loadTruckDetail() {
        if (!this.props.truckId) {
            this.state.error = "No Truck ID provided.";
            this.state.isLoading = false;
            return;
        }

        this.state.isLoading = true;
        try {
            // Use orm.read() to fetch a single record with its fields
            console.log("Fetching truck details for ID:", this.props.truckId);
            const truckData = await rpc(`/fleet/vehicle/safe/${this.props.truckId}`);
            console.log("Fetched truck data:", truckData);
            if (truckData.length) {
                this.state.truck = truckData[0];
            } else {
                this.state.error = "Truck not found.";
            }
        } catch (e) {
            console.error("Failed to load truck details:", e);
            this.state.error = "An error occurred while fetching truck details.";
        } finally {
            this.state.isLoading = false;
        }
    }

    async checkUserPermissions() {
        try {
            const result = await rpc('/provider/portal/trucks/can_edit_driver');
            this.state.canEditDriver = result.can_edit;
        } catch (e) {
            console.error('Failed to check user permissions:', e);
            this.state.canEditDriver = false;
        }
    }

    async openEditDriverModal() {
        this.state.showEditDriverModal = true;
        this.state.saveError = null;

        // Set current driver as selected
        this.state.selectedDriverId = this.state.truck.driver_id ? this.state.truck.driver_id[0].toString() : '';

        // Load available drivers
        await this.loadAvailableDrivers();
    }

    closeEditDriverModal() {
        this.state.showEditDriverModal = false;
        this.state.availableDrivers = [];
        this.state.selectedDriverId = '';
        this.state.saveError = null;
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
        } catch (e) {
            console.error('Failed to load available drivers:', e);
            this.state.availableDrivers = [];
        } finally {
            this.state.isLoadingDrivers = false;
        }
    }

    async saveDriver() {
        this.state.isSaving = true;
        this.state.saveError = null;

        try {
            const driverId = this.state.selectedDriverId ? parseInt(this.state.selectedDriverId) : false;

            // Update the driver using RPC
            await rpc('/provider/portal/trucks/update_driver', {
                truck_id: this.props.truckId,
                driver_id: driverId
            });

            // Reload truck details to reflect the change
            await this.loadTruckDetail();

            // Close modal
            this.closeEditDriverModal();
        } catch (e) {
            console.error('Failed to update driver:', e);
            this.state.saveError = 'Error al guardar el chofer. Por favor, intente nuevamente.';
        } finally {
            this.state.isSaving = false;
        }
    }
}

registry.category("components").add("ike_event_portal.TruckReadComponent", TruckReadComponent);