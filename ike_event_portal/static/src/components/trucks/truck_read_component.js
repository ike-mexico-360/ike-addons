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
        this.translate = _t;
        this.state = useState({
            truck: null,
            isLoading: true,
            canEditDriver: false,
            // Driver modal
            showEditDriverModal: false,
            availableDrivers: [],
            isLoadingDrivers: false,
            selectedDriverId: '',
            isSaving: false,
            // Vehicle type modal
            showEditVehicleTypeModal: false,
            availableVehicleTypes: [],
            selectedVehicleTypeId: '',
            // Center modal
            showEditCenterModal: false,
            availableCenters: [],
            selectedCenterId: '',
            // License plate modal
            showEditPlateModal: false,
            editedPlate: '',
            // Axes modal
            showEditAxesModal: false,
            editedAxes: 0,
            // Accessories modal
            showEditAccessoriesModal: false,
            editedManeuvers: false,
            editedFederalPlates: false,
            editedTireConditioning: false,
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

    // === VEHICLE TYPE ===
    async openEditVehicleTypeModal() {
        this.state.showEditVehicleTypeModal = true;
        this.state.selectedVehicleTypeId = this.state.truck.x_vehicle_type
            ? this.state.truck.x_vehicle_type[0].toString() : '';
        try {
            const result = await rpc('/provider/portal/trucks/vehicle_types');
            this.state.availableVehicleTypes = result.success ? result.vehicle_types : [];
        } catch (err) {
            this.state.availableVehicleTypes = [];
        }
    }

    closeEditVehicleTypeModal() {
        this.state.showEditVehicleTypeModal = false;
        this.state.selectedVehicleTypeId = '';
    }

    async saveVehicleType() {
        this.state.isSaving = true;
        try {
            const typeId = this.state.selectedVehicleTypeId ? parseInt(this.state.selectedVehicleTypeId) : false;
            const result = await rpc('/provider/portal/trucks/update_fields', {
                truck_id: this.props.truckId,
                fields: { x_vehicle_type: typeId }
            });
            if (!result.success) {
                this.showNotification({ title: _t("Error"), message: _t(result.error), type: 'danger' });
                return;
            }
            this.showNotification({ title: _t("Updated"), message: _t("Vehicle type updated."), type: 'success' });
            await this.loadTruckDetail();
            this.closeEditVehicleTypeModal();
        } catch (err) {
            this.showNotification({ title: _t("Error"), message: _t(err?.data?.message || err.message), type: 'danger' });
        } finally {
            this.state.isSaving = false;
        }
    }

    // === CENTER ===
    async openEditCenterModal() {
        this.state.showEditCenterModal = true;
        this.state.selectedCenterId = this.state.truck.x_center_id
            ? this.state.truck.x_center_id[0].toString() : '';
        try {
            const result = await rpc('/provider/portal/trucks/centers');
            this.state.availableCenters = result.success ? result.centers : [];
        } catch (err) {
            this.state.availableCenters = [];
        }
    }

    closeEditCenterModal() {
        this.state.showEditCenterModal = false;
        this.state.selectedCenterId = '';
    }

    async saveCenter() {
        this.state.isSaving = true;
        try {
            const centerId = this.state.selectedCenterId ? parseInt(this.state.selectedCenterId) : false;
            const result = await rpc('/provider/portal/trucks/update_fields', {
                truck_id: this.props.truckId,
                fields: { x_center_id: centerId }
            });
            if (!result.success) {
                this.showNotification({ title: _t("Error"), message: _t(result.error), type: 'danger' });
                return;
            }
            this.showNotification({ title: _t("Updated"), message: _t("Centro de atención updated."), type: 'success' });
            await this.loadTruckDetail();
            this.closeEditCenterModal();
        } catch (err) {
            this.showNotification({ title: _t("Error"), message: _t(err?.data?.message || err.message), type: 'danger' });
        } finally {
            this.state.isSaving = false;
        }
    }

    // === LICENSE PLATE ===
    openEditPlateModal() {
        this.state.editedPlate = this.state.truck.license_plate || '';
        this.state.showEditPlateModal = true;
    }

    closeEditPlateModal() {
        this.state.showEditPlateModal = false;
        this.state.editedPlate = '';
    }

    onPlateInput(ev) {
        this.state.editedPlate = ev.target.value;
    }

    async savePlate() {
        this.state.isSaving = true;
        try {
            const result = await rpc('/provider/portal/trucks/update_fields', {
                truck_id: this.props.truckId,
                fields: { license_plate: this.state.editedPlate }
            });
            if (!result.success) {
                this.showNotification({ title: _t("Error"), message: _t(result.error), type: 'danger' });
                return;
            }
            this.showNotification({ title: _t("Updated"), message: _t("Matrícula updated."), type: 'success' });
            await this.loadTruckDetail();
            this.closeEditPlateModal();
        } catch (err) {
            this.showNotification({ title: _t("Error"), message: _t(err?.data?.message || err.message), type: 'danger' });
        } finally {
            this.state.isSaving = false;
        }
    }

    // === AXES ===
    openEditAxesModal() {
        this.state.editedAxes = this.state.truck.x_vehicles_axes || 0;
        this.state.showEditAxesModal = true;
    }

    closeEditAxesModal() {
        this.state.showEditAxesModal = false;
        this.state.editedAxes = 0;
    }

    onAxesInput(ev) {
        this.state.editedAxes = parseInt(ev.target.value) || 0;
    }

    async saveAxes() {
        this.state.isSaving = true;
        try {
            const result = await rpc('/provider/portal/trucks/update_fields', {
                truck_id: this.props.truckId,
                fields: { x_vehicles_axes: this.state.editedAxes }
            });
            if (!result.success) {
                this.showNotification({ title: _t("Error"), message: _t(result.error), type: 'danger' });
                return;
            }
            this.showNotification({ title: _t("Guardado"), message: _t("Ejes actualizados."), type: 'success' });
            await this.loadTruckDetail();
            this.closeEditAxesModal();
        } catch (err) {
            this.showNotification({ title: _t("Error"), message: _t(err?.data?.message || err.message), type: 'danger' });
        } finally {
            this.state.isSaving = false;
        }
    }

    // === ACCESSORIES ===
    openEditAccessoriesModal() {
        this.state.editedManeuvers = this.state.truck.x_maneuvers || false;
        this.state.editedFederalPlates = this.state.truck.x_federal_license_plates || false;
        this.state.editedTireConditioning = this.state.truck.x_manages_tire_conditioning || false;
        this.state.showEditAccessoriesModal = true;
    }

    closeEditAccessoriesModal() {
        this.state.showEditAccessoriesModal = false;
    }

    async saveAccessories() {
        this.state.isSaving = true;
        try {
            const result = await rpc('/provider/portal/trucks/update_fields', {
                truck_id: this.props.truckId,
                fields: {
                    x_maneuvers: this.state.editedManeuvers,
                    x_federal_license_plates: this.state.editedFederalPlates,
                    x_manages_tire_conditioning: this.state.editedTireConditioning,
                }
            });
            if (!result.success) {
                this.showNotification({ title: _t("Error"), message: _t(result.error), type: 'danger' });
                return;
            }
            this.showNotification({ title: _t("Guardado"), message: _t("Accesorios actualizados."), type: 'success' });
            await this.loadTruckDetail();
            this.closeEditAccessoriesModal();
        } catch (err) {
            this.showNotification({ title: _t("Error"), message: _t(err?.data?.message || err.message), type: 'danger' });
        } finally {
            this.state.isSaving = false;
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