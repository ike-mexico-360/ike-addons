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
import { _t } from "@web/core/l10n/translation";

export class TrucksComponent extends Component {
    static template = "ike_event_portal.TrucksComponent";
    // Register the child component so we can use it in the template
    static components = { TruckReadComponent, TruckCreateComponent, PaginationComponent };



    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
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
            const trucksData = await this.orm.searchRead(
                'fleet.vehicle',
                [['x_partner_id', '=', this.supplier_id]],
                ['name', 'license_plate', 'model_id', 'x_partner_id', 'vehicle_type', 'brand_id', 'driver_id', 'x_vehicle_service_state', 'x_vehicle_type'],
                { context: { Lang: userLang }}
            );

            this.state.trucks = trucksData
                .map(truck => {
                    return {
                        ...truck,
                        x_vehicle_service_state_label: selectionMapping[truck.x_vehicle_service_state] || truck.x_vehicle_service_state
                    };
                });

        } catch (err) {
            this.showNotification({ title: _t("Error loading trucks"), message: _t(err?.data?.message || err.message || "An error occurred while loading the trucks."), type: 'danger' });
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

    showNotification({ message, type = 'info', sticky = true, title }) {
        this.notification.add(message, { type, sticky, title });
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
        } catch (err) {
            this.showNotification({ title: _t("Error obtaining supplier"), message: _t(err?.data?.message || err.message || "Error obtaining the associated provider."), type: 'danger' });
        }
    }

    updateFilter(field, value) {
        this.state.filters[field] = value;
    }

    async checkUserPermissions() {
        try {
            const result = await rpc('/provider/portal/trucks/can_add_driver');
            this.state.canAddDriver = result.can_edit;
        } catch (err) {
            this.showNotification({ title: _t("Error checking permissions"), message: _t(err?.data?.message || err.message || "An error occurred while checking user permissions."), type: 'danger' });
            this.state.canAddDriver = false;
        }
    }
}

registry.category("public_components").add("ike_event_portal.TrucksComponent", TrucksComponent);