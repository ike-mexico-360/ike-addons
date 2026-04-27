/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { TruckReadComponent } from "./truck_read_component";
import { TruckCreateComponent } from "./truck_create_component";
import { rpc } from "@web/core/network/rpc";
import { usePagination } from "../pagination/pagination_service";
import { PaginationComponent } from "../pagination/pagination_component";

export class TrucksComponent extends Component {
    static template = "ike_event_portal.TrucksComponent";
    // Register the child component so we can use it in the template
    static components = { TruckReadComponent, TruckCreateComponent, PaginationComponent };



    setup() {
        this.orm = useService("orm");
        this.supplier_id = 0;
        this.user = user;
        this.state = useState({
            trucks: [],
            isLoading: true,
            selectedTruckId: null,
            canAddDriver: false,
            view: 'list', // 'list', 'detail', or 'create',
            filters: {
                license_plate: "",
                model: "",
                driver: "",
            },
        });
        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredTrucks
        });

        onWillStart(async () => {
            await this.checkUserPermissions();
            await this.getSupplierId();
            await this.loadTrucks();
        });
    }

    // Method to show the details view
    showDetails(truckId) {
        this.state.selectedTruckId = truckId;
    }

    showCreateForm() {
        this.state.view = 'create';
    }

    // Method to go back to the list view
    showList() {
        this.state.selectedTruckId = null;
        this.state.view = 'list';
    }

    // Callback for when a truck is successfully created
    async onTruckCreated() {
        await this.loadTrucks(); // Refresh the list
        this.showList(); // Go back to the list view
    }

    async loadTrucks() {
        // ... (loadTrucks method remains the same)
        this.state.isLoading = true;
        const userLang = this.user.lang || 'es_MX';
        let selectionMapping = {};
        try {
            // 1. Call to obtain the translations of the Selection
            const fieldsData = await this.orm.call('fleet.vehicle', 'fields_get', [['x_vehicle_service_state']], {
                attributes: ['selection'],
                context: { lang: userLang }
            });

            // We verify that the response has what we expect.
            if (fieldsData && fieldsData.x_vehicle_service_state && fieldsData.x_vehicle_service_state.selection) {
                fieldsData.x_vehicle_service_state.selection.forEach(([key, label]) => {
                    selectionMapping[key] = label;
                });
            }
            console.log(' selectionMapping...',  selectionMapping);
            const trucksData = await this.orm.searchRead(
                'fleet.vehicle',
                [],
                ['name', 'license_plate', 'model_id', 'x_partner_id', 'vehicle_type', 'brand_id', 'driver_id', 'x_vehicle_service_state', 'x_vehicle_type'],
                { context: { Lang: userLang }}
            );

            this.state.trucks = trucksData
                .filter(x => x.x_partner_id && x.x_partner_id.includes(this.supplier_id))
                .map(truck => {
                    return {
                        ...truck,
                        x_vehicle_service_state_label: selectionMapping[truck.x_vehicle_service_state] || truck.x_vehicle_service_state
                    };
                });
            console.log('Trucks...', this.state.trucks);
            // console.log('Trucks...', trucksData.filter(x => x.x_partner_id && x.x_partner_id.includes(this.supplier_id)));
            // this.state.trucks = trucksData.filter(x => x.x_partner_id && x.x_partner_id.includes(this.supplier_id));
        } catch (e) {
            console.error("Failed to load trucks:", e);
        } finally {
            this.state.isLoading = false;
        }
    }

    get filteredTrucks() {
        const { trucks, filters } = this.state;
        // Convert search terms to lowercase for case-insensitive search
        const searchLicense = filters.license_plate.toLowerCase().trim();
        const searchModel = filters.model.toLowerCase().trim();
        const searchDriver = filters.driver.toLowerCase().trim();

        return trucks.filter(truck => {
            // 1. Check License Plate
            // Note: Ensure truck.license_plate exists before calling toLowerCase()
            const matchLicense = !searchLicense ||
                (truck.license_plate && truck.license_plate.toLowerCase().includes(searchLicense));

            // 2. Check Model
            // Note: truck.model_id is usually a Many2one array: [id, "Name"]
            const modelName = Array.isArray(truck.model_id) ? truck.model_id[1] : (truck.model_id || "");
            const matchModel = !searchModel ||
                modelName.toLowerCase().includes(searchModel);

            // 3. Check Driver
            // Note: truck.driver_id is usually a Many2one array: [id, "Name"]
            const driverName = Array.isArray(truck.driver_id) ? truck.driver_id[1] : (truck.driver_id || "");
            const matchDriver = !searchDriver ||
                driverName.toLowerCase().includes(searchDriver);

            // Return true only if ALL conditions match
            return matchLicense && matchModel && matchDriver;
        });
    }

    async getSupplierId() {
        try {
            let supplier_drivers = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [],
                []
            );
            let supplier = supplier_drivers.find(x => x.user_id && x.user_id[0] === this.user.userId);
            if(!supplier) {
                this.state.notification = { type: 'warning', message: 'El usuario no está asociado a ningún proveedor.' };
                return;
            }
            this.supplier_id = supplier.supplier_id[0];
        }
        catch (e) {
            this.state.notification = { type: 'error', message: 'Error al obtener el proveedor asociado.' };
        }

    }

    closeNotification() {
        this.state.notification = null;
    }

    updateFilter(field, value) {
        this.state.filters[field] = value;
    }

    async checkUserPermissions() {
        try {
            const result = await rpc('/provider/portal/trucks/can_add_driver');
            this.state.canAddDriver = result.can_edit;
        } catch (e) {
            console.error('Failed to check user permissions:', e);
            this.state.canAddDriver = false;
        }
    }
}

registry.category("public_components").add("ike_event_portal.TrucksComponent", TrucksComponent);