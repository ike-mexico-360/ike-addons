/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";

export class TruckCreateComponent extends Component {
    static template = "ike_event_portal.TruckCreateComponent";
    static props = {
        onTruckCreated: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
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
            error: null
        });

        onWillStart(async () => {
            // Use Promise.all to fetch all data in parallel for better performance
            await this.getSupplierId();
            //await this.loadDrivers();
            await this.loadSupplierCenters();
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

            // Assign fetched data to the component's state
            this.state.models = modelsData;
            this.state.suppliers = suppliersData;
            this.state.vehicle_types = vehicleTypesData;
            this.state.service_states = fieldsData.x_vehicle_service_state.selection;
            this.state.accessories = accessoriesResult.success ? accessoriesResult.accessories : [];
        });
    }

    async saveTruck() {
        this.state.error = null;
        this.state.isSubmitting = true;

        if (this.supplier_id === 0) {
            this.state.error = "No se pudo determinar el proveedor. Por favor, contacte al administrador.";
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
            console.log('Payload for truck creation:', payload);
            await this.orm.create('fleet.vehicle', [payload]);
            this.props.onTruckCreated();
        } catch (err) {
            console.error("Error creating truck:", err);
            this.state.error = "Error saving truck. Please check the console.";
        } finally {
            this.state.isSubmitting = false;
        }
    }

    async getSupplierId() {
        try {
            let supplier_drivers = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [],
                []
            );
            let supplier = supplier_drivers.find(x => x.user_id && x.user_id[0] === this.user.userId);
            if (!supplier) {
                this.state.notification = { type: 'warning', message: 'El usuario no está asociado a ningún proveedor.' };
                return;
            }
            this.supplier_id = supplier.supplier_id[0];
            this.supplier_name = supplier.supplier_id[1];
        }
        catch (e) {
            this.state.notification = { type: 'error', message: 'Error al obtener el proveedor asociado.' };
        }

    }

    closeNotification() {
        this.state.notification = null;
    }

    async onCenterOfAttentionChange(ev) {
        const centerId = ev.target.value;
        this.state.formData.center_of_attention_id = centerId;
        if (centerId) {
            // Replace with your actual route and params
            const drivers = await rpc("/provider/portal/trucks/available_drivers", { center_of_attention_id: parseInt(centerId) });
            console.log('Available Drivers:', drivers);
            this.state.drivers = drivers;
        } else {
            this.state.drivers = [];
        }
    }

    async loadDrivers() {

        const drivers = await rpc('/provider/portal/trucks/available_drivers', {
            supplier_id: this.supplier_id
        });

        console.log('Available Drivers:', drivers);
        this.state.drivers = drivers;
    }

    async loadSupplierCenters() {
        console.log('Loading supplier centers for partner ID:', this.supplier_id);
        try {
            const result = await rpc('/api/partners/centers', {
                partner_id: this.supplier_id
            });

            console.log('Supplier Centers:', result);
            this.state.supplierCenters = result; // Store in state if needed
            return result;
        } catch (error) {
            console.error('Error loading supplier centers:', error);
            this.state.error = 'Error loading supplier centers';
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