/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

export class TruckCreateComponent extends Component {
    static template = "ike_event_portal.TruckCreateComponent";
    static props = {
        onTruckCreated: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.supplier_id = 0;
        this.supplier_name = "";
        this.user = user;
        this.state = useState({
            formData: {
                name: "",
                license_plate: "",
                model_id: "", // Assuming model_id is a Many2one to fleet.vehicle.model
                driver_id: "",
                center_of_attention_id: "",
                accessories: [],
                x_vehicles_axes: 0,
                x_manages_tire_conditioning: false,
            },
            models: [],
            suppliers: [],
            vehicle_types: [],
            drivers: [],
            service_states: [],
            accessories: [],
            isSubmitting: false,
        });

        onWillStart(async () => {
            await this.getSupplierId();
            await this.loadSupplierCenters();
            try {
                const [
                    modelsData,
                    suppliersData,
                    vehicleTypesData,
                    fieldsData,
                    accessoriesResult
                ] = await Promise.all([
                    this.orm.searchRead('fleet.vehicle.model', [], []),
                    this.orm.searchRead('res.partner', [['x_is_supplier', '=', true], ['disabled', '=', false]], ['name']),
                    this.orm.searchRead('custom.vehicle.type', [['disabled', '=', false]], ['name']),
                    this.orm.call('fleet.vehicle', 'fields_get', [['x_vehicle_service_state']], {}),
                    rpc('/provider/portal/trucks/accessories', {})
                ]);

                this.state.models = modelsData;
                this.state.suppliers = suppliersData;
                this.state.vehicle_types = vehicleTypesData;
                this.state.service_states = fieldsData.x_vehicle_service_state.selection;
                this.state.accessories = accessoriesResult.success ? accessoriesResult.accessories : [];
            } catch (err) {
                this.showNotification({ title: _t("Error loading form data"), message: _t(err?.data?.message || err.message || "An error occurred while loading the form data."), type: 'danger' });
            }
        });
    }

    showNotification({ message, type = 'info', sticky = true, title }) {
        this.notification.add(message, { type, sticky, title });
    }

    async saveTruck() {
        this.state.isSubmitting = true;

        if (this.supplier_id === 0) {
            this.showNotification({ title: _t("Supplier not found"), message: _t("The provider could not be determined. Please contact the administrator."), type: 'warning' });
            this.state.isSubmitting = false;
            return;
        }

        if(!this.state.formData.x_maneuvers) {
           this.state.formData.accessories = [];
        }

        try {
            const payload = {
                name: this.state.formData.name,
                license_plate: this.state.formData.license_plate,
                model_id: parseInt(this.state.formData.model_id),
                driver_id: this.state.formData.driver_id ? parseInt(this.state.formData.driver_id) : false,
                x_partner_id: this.supplier_id,
                x_vehicle_type: this.state.formData.x_vehicle_type ? parseInt(this.state.formData.x_vehicle_type) : false,
                // ... other fields ...
                x_vehicle_service_state: this.state.formData.x_vehicle_service_state,
                x_federal_license_plates: this.state.formData.x_federal_license_plates,
                x_maneuvers: this.state.formData.x_maneuvers,
                x_vehicles_axes: parseInt(this.state.formData.x_vehicles_axes) || 0,
                x_center_id: this.state.formData.center_of_attention_id ? parseInt(this.state.formData.center_of_attention_id) : false,
                x_accessories: [[6, 0, this.state.formData.accessories.map(id => parseInt(id))]],
                x_manages_tire_conditioning: this.state.formData.x_manages_tire_conditioning
            };
            await this.orm.create('fleet.vehicle', [payload]);
            this.showNotification({ title: _t("Truck created"), message: _t("The truck has been created successfully."), type: 'success' });
            this.props.onTruckCreated();
        } catch (err) {
            this.showNotification({ title: _t("Error saving truck"), message: _t(err?.data?.message || err.message || "An error occurred while saving the truck."), type: 'danger' });
        } finally {
            this.state.isSubmitting = false;
        }
    }

    async getSupplierId() {
        try {
            const [supplier] = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [['user_id', '=', this.user.userId]],
                ['supplier_id'],
                { limit: 1 }
            );
            if (!supplier) {
                this.showNotification({ title: _t("Supplier not found"), message: _t("The user is not associated with any provider."), type: 'warning' });
                return;
            }
            this.supplier_id = supplier.supplier_id[0];
            this.supplier_name = supplier.supplier_id[1];
        } catch (err) {
            this.showNotification({ title: _t("Error obtaining supplier"), message: _t(err?.data?.message || err.message || "Error obtaining the associated provider."), type: 'danger' });
        }
    }

    async onCenterOfAttentionChange(ev) {
        const centerId = ev.target.value;
        this.state.formData.center_of_attention_id = centerId;
        if (centerId) {
            try {
                const drivers = await rpc("/provider/portal/trucks/available_drivers", { center_of_attention_id: parseInt(centerId) });
                this.state.drivers = drivers;
            } catch (err) {
                this.showNotification({ title: _t("Error loading drivers"), message: _t(err?.data?.message || err.message || "An error occurred while loading the available drivers."), type: 'danger' });
                this.state.drivers = [];
            }
        } else {
            this.state.drivers = [];
        }
    }

    async loadDrivers() {
        try {
            const drivers = await rpc('/provider/portal/trucks/available_drivers', {
                supplier_id: this.supplier_id
            });
            this.state.drivers = drivers;
        } catch (err) {
            this.showNotification({ title: _t("Error loading drivers"), message: _t(err?.data?.message || err.message || "An error occurred while loading the drivers."), type: 'danger' });
            this.state.drivers = [];
        }
    }

    async loadSupplierCenters() {
        try {
            const result = await rpc('/api/partners/centers', {
                partner_id: this.supplier_id
            });
            this.state.supplierCenters = result;
            return result;
        } catch (err) {
            this.showNotification({ title: _t("Error loading supplier centers"), message: _t(err?.data?.message || err.message || "An error occurred while loading the supplier centers."), type: 'danger' });
        }
    }

    toggleAccessory(accessoryId, isChecked) {
        if (isChecked) {
            if (!this.state.formData.accessories.includes(accessoryId)) {
                this.state.formData.accessories.push(accessoryId);
            }
        } else {
            const index = this.state.formData.accessories.indexOf(accessoryId);
            if (index > -1) {
                this.state.formData.accessories.splice(index, 1);
            }
        }
    }
}

registry.category("public_components").add("ike_event_portal.TruckCreateComponent", TruckCreateComponent);