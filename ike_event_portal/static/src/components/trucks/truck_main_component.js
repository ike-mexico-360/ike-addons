/** @odoo-module **/

import { Component, markup, onWillStart, useExternalListener, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { TruckReadComponent } from "./truck_read_component";
import { TruckCreateComponent } from "./truck_create_component";
import { rpc } from "@web/core/network/rpc";
import { usePagination } from "../pagination/pagination_service";
import { PaginationComponent } from "../pagination/pagination_component";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

// Economic number and row actions are mandatory and therefore absent here.
const OPTIONAL_TRUCK_COLUMNS = [
    { key: "license_plate", label: _t("License plate") },
    { key: "model", label: _t("Make / model / year") },
    { key: "vehicle_type", label: _t("Vehicle type") },
    { key: "driver", label: _t("Driver") },
    { key: "state", label: _t("Status") },
    { key: "current_event", label: _t("Current event") },
    { key: "last_change", label: _t("Last change") },
];

export class TrucksComponent extends Component {
    static template = "ike_event_portal.TrucksComponent";
    // Register the child component so we can use it in the template
    static components = { TruckReadComponent, TruckCreateComponent, PaginationComponent };



    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");
        this.supplier_id = 0;
        this.user = user;
        this.state = useState({
            trucks: [],
            isLoading: true,
            selectedTruckId: null,
            canAddDriver: false,
            canEditUnitStatus: false,
            canPermanentlyDeregister: false,
            permanentDeregistrationEligibility: {},
            updatingTruckId: null,
            actionsMenuTruckId: null,
            deregistration: {
                showRequest: false,
                showCode: false,
                truck: null,
                reason: '',
                reasons: [],
                licensePlate: '',
                evidence: [],
                evidenceName: '',
                warningEvents: [],
                isLastUnitOfType: false,
                code: '',
                isSaving: false,
            },
            temporaryDowntime: { show: false, truck: null, reason: '', reasons: [], returnDate: '', isSaving: false },
            deregistrationHistory: { show: false, data: null },
            eventSummary: { show: false, isLoading: false, eventName: "", stage: "", html: "" },
            view: 'list', // 'list', 'detail', or 'create',
            filters: {
                search: "",
                vehicle_type: "",
                vehicle_state: "",
            },
            sort: { column: 'economic_number', direction: 'asc' },
            vehicleStateOptions: [],
            visibleColumns: OPTIONAL_TRUCK_COLUMNS.map((column) => column.key),
            columnMenuOpen: false,
            isSavingColumnPreferences: false,
            header: {
                supplierName: "",
                supplierRfc: "",
                centers: [],
                selectedCenterId: null,
                centerMenuOpen: false,
                userName: "",
                userEmail: "",
                userRole: "",
            },
        });
        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredTrucks
        });

        // Close the row actions menu when clicking anywhere else.
        useExternalListener(window, "click", () => {
            this.state.actionsMenuTruckId = null;
            this.state.columnMenuOpen = false;
        });

        onWillStart(async () => {
            await this.checkUserPermissions();
            await this.getSupplierId();
            await Promise.all([
                this.loadTrucks(),
                this.loadHeaderInfo(),
                this.loadColumnPreferences(),
                this.loadDeregistrationReasons(),
            ]);
        });
    }

    async loadDeregistrationReasons() {
        const result = await rpc('/provider/portal/trucks/deregistration/reasons', {});
        this.state.deregistration.reasons = result?.reasons || [];
    }

    /** Loads the saved selection for this portal user, or all optional columns by default. */
    async loadColumnPreferences() {
        try {
            const result = await rpc('/provider/portal/trucks/column_preferences', {});
            if (result?.success && Array.isArray(result.visible_columns)) {
                this.state.visibleColumns = this.normalizeVisibleColumns(result.visible_columns);
            }
        } catch (error) {
            // A preference failure must never prevent the vehicle list from loading.
            console.warn('Unable to load truck column preferences:', error);
        }
    }

    normalizeVisibleColumns(columns) {
        return OPTIONAL_TRUCK_COLUMNS
            .map((column) => column.key)
            .filter((column) => columns.includes(column));
    }

    isColumnVisible(column) {
        return this.state.visibleColumns.includes(column);
    }

    get truckColumnCount() {
        // One mandatory economic-number column, selected optional columns, and actions.
        return this.state.visibleColumns.length + 2;
    }

    get optionalTruckColumns() {
        return OPTIONAL_TRUCK_COLUMNS;
    }

    toggleColumnMenu() {
        this.state.columnMenuOpen = !this.state.columnMenuOpen;
    }

    async toggleColumn(column, checked) {
        const previousColumns = [...this.state.visibleColumns];
        const updatedColumns = checked
            ? [...previousColumns, column]
            : previousColumns.filter((visibleColumn) => visibleColumn !== column);

        this.state.visibleColumns = this.normalizeVisibleColumns(updatedColumns);
        this.state.isSavingColumnPreferences = true;
        try {
            const result = await rpc('/provider/portal/trucks/column_preferences', {
                visible_columns: this.state.visibleColumns,
            });
            if (!result?.success) {
                throw new Error(result?.error || _t('Unable to save column preferences.'));
            }
            this.state.visibleColumns = this.normalizeVisibleColumns(result.visible_columns);
        } catch (error) {
            this.state.visibleColumns = previousColumns;
            this.showNotification({
                title: _t('Error'),
                message: error.message || _t('Unable to save column preferences.'),
                type: 'danger',
            });
        } finally {
            this.state.isSavingColumnPreferences = false;
        }
    }

    async loadHeaderInfo() {
        try {
            const header = this.state.header;

            const [[userData], roleLabel] = await Promise.all([
                this.orm.searchRead('res.users', [['id', '=', this.user.userId]], ['name', 'email']),
                this.getUserRoleLabel(),
            ]);
            // The client-side user singleton's name can come back empty on website/portal
            // pages (its session info is seeded differently than the backend webclient),
            // so fetch it directly via ORM instead of trusting this.user.name.
            header.userName = (userData && userData.name) || this.user.name || "";
            header.userEmail = (userData && userData.email) || "";
            header.userRole = roleLabel;

            if (!this.supplier_id) return;

            const [supplier] = await this.orm.searchRead(
                'res.partner',
                [['id', '=', this.supplier_id]],
                ['name', 'vat', 'x_supplier_center_ids']
            );
            if (!supplier) return;

            header.supplierName = supplier.name || "";
            header.supplierRfc = supplier.vat || "";

            if (supplier.x_supplier_center_ids && supplier.x_supplier_center_ids.length) {
                const centers = await this.orm.searchRead(
                    'res.partner',
                    [['id', 'in', supplier.x_supplier_center_ids]],
                    ['name']
                );
                header.centers = centers;
                header.selectedCenterId = null;
            }
        } catch (err) {
            // Non-blocking: the header is informational, the page still works without it.
            console.warn("Error loading header info:", err);
        }
    }

    async getUserRoleLabel() {
        const roleGroups = [
            ['ike_event_portal.custom_group_portal_admin', _t("Provider administrator")],
            ['ike_event_portal.custom_group_portal_supervisor', _t("Provider supervisor")],
            ['ike_event_portal.custom_group_portal_finance', _t("Provider finance")],
            ['ike_event_portal.custom_group_portal_operator', _t("Provider operator")],
        ];
        for (const [group, label] of roleGroups) {
            if (await user.hasGroup(group)) {
                return label;
            }
        }
        return _t("Provider user");
    }

    get selectedCenterName() {
        if (!this.state.header.selectedCenterId) return _t("All centers");
        const center = this.state.header.centers.find(c => c.id === this.state.header.selectedCenterId);
        return center ? center.name : "";
    }

    get userInitials() {
        // res.partner has no separate firstname/lastname fields here, only the
        // combined name, so the first word is taken as the first name and the
        // last word as the last name (handles compound Hispanic last names better
        // than just taking the first two words).
        const name = this.state.header.userName.trim();
        if (!name) return "";
        const parts = name.split(/\s+/);
        const firstName = parts[0];
        const lastName = parts[parts.length - 1];
        console.log('firstName: ', firstName);
        console.log('lastName: ', lastName);
        if (parts.length === 1) return firstName[0].toUpperCase();
        return (firstName[0] + lastName[0]).toUpperCase();
    }

    async logout() {
        window.location.href = "/web/session/logout?redirect=/";
    }

    selectCenter(centerId) {
        this.state.header.selectedCenterId = centerId;
        this.state.header.centerMenuOpen = false;
    }

    toggleCenterMenu() {
        this.state.header.centerMenuOpen = !this.state.header.centerMenuOpen;
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
        try {
            const trucksData = await this.orm.searchRead(
                'fleet.vehicle',
                [['x_partner_id', '=', this.supplier_id]],
                [
                    'name', 'license_plate', 'model_id', 'x_partner_id', 'vehicle_type', 'brand_id',
                    'driver_id', 'x_vehicle_service_state', 'x_vehicle_type', 'x_economic_number', 'model_year',
                    'x_vehicle_ref', 'x_center_id', 'x_federal_license_plates', 'x_current_event_info',
                ],
                { order: 'x_economic_number asc, id asc' }
            );

            // Selection labels come from the server, translated by the module's i18n files.
            const fieldsData = await this.orm.call('fleet.vehicle', 'fields_get', [['x_vehicle_service_state']], {
                attributes: ['selection'],
            });
            const selection = fieldsData?.x_vehicle_service_state?.selection || [];
            const stateLabels = Object.fromEntries(selection);
            this.state.vehicleStateOptions = selection;

            // Last status change from the chatter log; the column is optional, so a failure here
            // must not block the list.
            let lastChanges = {};
            if (trucksData.length) {
                const changesResult = await rpc('/provider/portal/trucks/last_state_changes', {
                    truck_ids: trucksData.map(truck => truck.id),
                }).catch(err => console.warn("Error loading last status changes:", err));
                if (changesResult?.success) {
                    lastChanges = changesResult.changes;
                }
            }

            this.state.trucks = trucksData
                .map(truck => {
                    const lastChange = lastChanges[truck.id];
                    const eventInfo = truck.x_current_event_info;
                    return {
                        ...truck,
                        current_event: eventInfo
                            ? { event_id: eventInfo.event_id, name: eventInfo.event_name, stage: eventInfo.stage_name }
                            : null,
                        x_vehicle_service_state_label: _t(stateLabels[truck.x_vehicle_service_state] || truck.x_vehicle_service_state),
                        // UTC 'YYYY-MM-DD HH:MM:SS' string, sortable as text.
                        last_state_change_raw: lastChange ? lastChange.date : "",
                        last_state_change_date: lastChange ? formatDateTime(deserializeDateTime(lastChange.date)) : "",
                        last_state_change_user: lastChange ? (lastChange.is_system ? _t("System") : lastChange.user) : "",
                    };
                });

            if (this.state.canPermanentlyDeregister && trucksData.length) {
                const eligibility = await rpc('/provider/portal/trucks/deregistration/eligibility', {
                    truck_ids: trucksData.map(truck => truck.id),
                });
                this.state.permanentDeregistrationEligibility = eligibility?.success
                    ? eligibility.eligible || {}
                    : {};
            } else {
                this.state.permanentDeregistrationEligibility = {};
            }

            console.log("Loaded trucks:", this.state.trucks);

        } catch (err) {
            this.showNotification({ title: _t("Error loading trucks"), message: _t(err?.data?.message || err.message || "An error occurred while loading the trucks."), type: 'danger' });
        } finally {
            this.state.isLoading = false;
        }
    }

    get filteredTrucks() {
        // Permanently deregistered units stay out of the default list, but remain
        // auditable by selecting their state in the existing status filter.
        const showDeregistered = this.state.filters.vehicle_state === 'deregistration';
        return this.sortTrucks(this.state.trucks.filter(truck =>
            (showDeregistered || truck.x_vehicle_service_state !== 'deregistration')
            && this.matchesFilters(truck)
        ));
    }

    // Centro de atención, search box, vehicle type and vehicle state filters.
    matchesFilters(truck) {
        const { filters, header } = this.state;
        // Convert search terms to lowercase for case-insensitive search
        const search = filters.search.toLowerCase().trim();
        const searchVehicleType = filters.vehicle_type;
        const searchVehicleState = filters.vehicle_state;
        const selectedCenterId = header.selectedCenterId;

        // 0. Check Centro de atención
        const centerId = Array.isArray(truck.x_center_id) ? truck.x_center_id[0] : truck.x_center_id;
        const matchCenter = !selectedCenterId || centerId === selectedCenterId;
        if (!matchCenter) return false;

        // 1. Combined search: license plate, economic number, driver, UUID
        const driverName = Array.isArray(truck.driver_id) ? truck.driver_id[1] : (truck.driver_id || "");
        const matchSearch = !search || [
            truck.license_plate,
            truck.x_economic_number,
            driverName,
            truck.x_vehicle_ref,
        ].some(value => value && value.toLowerCase().includes(search));

        // 2. Check Vehicle Type (exact match against the select value)
        const vehicleTypeId = Array.isArray(truck.x_vehicle_type) ? truck.x_vehicle_type[0] : truck.x_vehicle_type;
        const matchVehicleType = !searchVehicleType ||
            String(vehicleTypeId) === String(searchVehicleType);

        // 3. Check Vehicle State
        const matchVehicleState = !searchVehicleState ||
            truck.x_vehicle_service_state === searchVehicleState;

        // Return true only if ALL conditions match
        return matchSearch && matchVehicleType && matchVehicleState;
    }

    // Value used to sort each column, as shown in the table.
    sortValue(truck, column) {
        const name = (value) => (Array.isArray(value) ? value[1] : value) || "";
        switch (column) {
            case 'economic_number': return truck.x_economic_number || "";
            case 'license_plate': return truck.license_plate || "";
            case 'model': return `${name(truck.model_id)} ${truck.model_year || ""}`;
            case 'vehicle_type': return name(truck.x_vehicle_type);
            case 'driver': return name(truck.driver_id);
            case 'state': return truck.x_vehicle_service_state_label || "";
            case 'current_event': return truck.current_event ? truck.current_event.name : "";
            case 'last_change': return truck.last_state_change_raw || "";
            default: return "";
        }
    }

    sortTrucks(trucks) {
        const { column, direction } = this.state.sort;
        const factor = direction === 'asc' ? 1 : -1;
        return [...trucks].sort((a, b) => {
            const valueA = this.sortValue(a, column);
            const valueB = this.sortValue(b, column);
            // Empty values always go last, whatever the direction.
            if (!valueA || !valueB) {
                return !valueA - !valueB;
            }
            // numeric: true so "9" sorts before "10".
            return factor * String(valueA).localeCompare(String(valueB), undefined, { numeric: true, sensitivity: 'base' });
        });
    }

    // Exports every truck matching the current filters (all pages), in the current sort order.
    downloadExcel() {
        const ids = this.filteredTrucks.map(truck => truck.id).join(',');
        window.open(`/provider/portal/trucks/download/xlsx?ids=${ids}`, '_blank');
    }

    // The detailed export is independent from the columns visible in the table.
    downloadDetailedExcel() {
        const ids = this.filteredTrucks.map(truck => truck.id).join(',');
        window.open(`/provider/portal/trucks/download/detailed/xlsx?ids=${ids}`, '_blank');
    }

    toggleSort(column) {
        const sort = this.state.sort;
        if (sort.column === column) {
            sort.direction = sort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            sort.column = column;
            sort.direction = 'asc';
        }
        this.pagination.reset();
    }

    sortIcon(column) {
        const { column: current, direction } = this.state.sort;
        if (current !== column) {
            return 'fa fa-sort text-muted';
        }
        return direction === 'asc' ? 'fa fa-sort-asc' : 'fa fa-sort-desc';
    }

    get vehicleTypeOptions() {
        const seen = new Map();
        for (const truck of this.state.trucks) {
            if (Array.isArray(truck.x_vehicle_type)) {
                seen.set(truck.x_vehicle_type[0], truck.x_vehicle_type[1]);
            }
        }
        return Array.from(seen.entries());
    }

    clearFilters() {
        this.state.filters.search = "";
        this.state.filters.vehicle_type = "";
        this.state.filters.vehicle_state = "";
    }

    get truckStats() {
        // Counts follow every active filter (centro de atención, search box, vehicle type and
        // vehicle state), and exclude permanently deregistered units.
        const activeTrucks = this.state.trucks.filter(truck =>
            truck.x_vehicle_service_state !== 'deregistration' && this.matchesFilters(truck)
        );
        const countByState = (state) => activeTrucks.filter(truck => truck.x_vehicle_service_state === state).length;
        return {
            total: activeTrucks.length,
            available: countByState('available'),
            in_service: countByState('in_service'),
            not_available: countByState('not_available'),
            disabled: countByState('disabled'),
        };
    }

    // Literal _t() calls so Odoo's translation export picks the strings up.
    truckModelName(truck) {
        return truck.model_id ? truck.model_id[1] : _t("Generic");
    }

    truckDriverName(truck) {
        return truck.driver_id ? truck.driver_id[1] : _t("Unassigned");
    }


    showNotification({ message, type = 'info', sticky = true, title }) {
        this.notification.add(message, { type, sticky, title });
    }

    canEditVehicleStatus(truck) {
        return this.state.canEditUnitStatus && ['available', 'not_available'].includes(truck.x_vehicle_service_state);
    }

    vehicleStatusLabel(state) {
        const truck = this.state.trucks.find(item => item.x_vehicle_service_state === state);
        if (truck) {
            return truck.x_vehicle_service_state_label;
        }
        return state === 'available' ? _t('Available') : _t('Not Available');
    }

    async openEventSummary(truck) {
        const summary = this.state.eventSummary;
        Object.assign(summary, {
            show: true,
            isLoading: true,
            eventName: truck.current_event.name,
            stage: truck.current_event.stage,
            html: "",
        });
        try {
            const result = await rpc('/provider/portal/trucks/current_event_summary', { truck_id: truck.id });
            if (!result.success) {
                this.closeEventSummary();
                this.showNotification({ title: _t('Error'), message: result.error, type: 'danger' });
                return;
            }
            summary.eventName = result.event_name;
            summary.stage = result.stage;
            // Html field, sanitized on the server.
            summary.html = markup(result.summary);
        } catch (err) {
            this.closeEventSummary();
            this.showNotification({ title: _t('Error'), message: err?.data?.message || err.message, type: 'danger' });
        } finally {
            summary.isLoading = false;
        }
    }

    closeEventSummary() {
        this.state.eventSummary.show = false;
    }

    toggleActionsMenu(truckId) {
        this.state.actionsMenuTruckId = this.state.actionsMenuTruckId === truckId ? null : truckId;
    }

    onChangeStatusClick(truck) {
        this.state.actionsMenuTruckId = null;
        this.openVehicleStatusConfirmation(truck);
    }

    canDeregisterTruck(truck) {
        return this.state.canPermanentlyDeregister
            && this.state.permanentDeregistrationEligibility[truck.id] === true;
    }

    async onPermanentDeregistrationClick(truck) {
        this.state.actionsMenuTruckId = null;
        if (!this.canDeregisterTruck(truck)) {
            return;
        }
        try {
            const result = await rpc('/provider/portal/trucks/deregistration/check', { truck_id: truck.id });
            if (!result.success) {
                this.showNotification({ title: _t("Unable to permanently deregister unit"), message: result.error, type: 'danger' });
                return;
            }
            Object.assign(this.state.deregistration, {
                showRequest: true,
                showCode: false,
                truck: result.truck,
                reason: '',
                licensePlate: '',
                evidence: [],
                evidenceName: '',
                warningEvents: result.warning_events || [],
                isLastUnitOfType: !!result.is_last_unit_of_type,
                code: '',
                isSaving: false,
            });
        } catch (error) {
            this.showNotification({ title: _t('Error'), message: error?.data?.message || error.message, type: 'danger' });
        }
    }

    async openDeregistrationHistory(truck) {
        const result = await rpc('/provider/portal/trucks/deregistration/history', { truck_id: truck.id });
        if (!result.success) {
            this.showNotification({ title: _t('Error'), message: result.error, type: 'danger' });
            return;
        }
        this.state.deregistrationHistory = { show: true, data: result.history };
    }

    closeDeregistrationModals() {
        Object.assign(this.state.deregistration, {
            showRequest: false, showCode: false, truck: null, reason: '', licensePlate: '',
            evidence: [], evidenceName: '', warningEvents: [], isLastUnitOfType: false, code: '', isSaving: false,
        });
    }

    async onDeregistrationEvidenceChange(event) {
        const files = Array.from(event.target.files || []);
        if (!files.length) {
            this.state.deregistration.evidence = [];
            this.state.deregistration.evidenceName = '';
            return;
        }
        const maxFiles = 4;
        const maxSize = 3 * 1024 * 1024;
        if (files.length > maxFiles) {
            event.target.value = '';
            this.showNotification({ title: _t("Evidence"), message: _t("At most 4 evidence files can be attached."), type: 'warning' });
            return;
        }
        if (files.some((file) => file.size > maxSize)) {
            event.target.value = '';
            this.showNotification({ title: _t("Evidence"), message: _t("Each evidence file must be 3 MB or smaller."), type: 'warning' });
            return;
        }
        try {
            const evidence = await Promise.all(files.map(async (file) => {
                const content = await new Promise((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(String(reader.result).split(',')[1]);
                    reader.onerror = reject;
                    reader.readAsDataURL(file);
                });
                return { name: file.name, data: content, mimetype: file.type };
            }));
            this.state.deregistration.evidence = evidence;
            this.state.deregistration.evidenceName = evidence.map((file) => file.name).join(', ');
        } catch (error) {
            event.target.value = '';
            this.state.deregistration.evidence = [];
            this.state.deregistration.evidenceName = '';
            this.showNotification({ title: _t("Evidence"), message: _t("The evidence file could not be read."), type: 'danger' });
        }
    }

    async requestDeregistrationCode() {
        const data = this.state.deregistration;
        if (!data.reason || !data.evidence.length || !data.licensePlate.trim()) {
            this.showNotification({ title: _t("Required information"), message: _t("Select a reason, attach evidence, and confirm the license plate."), type: 'warning' });
            return;
        }
        data.isSaving = true;
        try {
            const result = await rpc('/provider/portal/trucks/deregistration/request_code', {
                truck_id: data.truck.id,
                reason: data.reason,
                license_plate: data.licensePlate,
                evidence: data.evidence,
            });
            if (!result.success) {
                this.showNotification({ title: _t("Unable to request verification code"), message: result.error, type: 'danger' });
                return;
            }
            data.showRequest = false;
            data.showCode = true;
            data.code = '';
            this.showNotification({ title: _t("Verification code sent"), message: _t("A verification code was sent by email and portal notification. It expires in 10 minutes."), type: 'success' });
        } catch (error) {
            this.showNotification({ title: _t('Error'), message: error?.data?.message || error.message, type: 'danger' });
        } finally {
            data.isSaving = false;
        }
    }

    async confirmPermanentDeregistration() {
        const data = this.state.deregistration;
        if (!data.code.trim()) {
            this.showNotification({ title: _t("Verification code required"), message: _t("Enter the six-digit verification code."), type: 'warning' });
            return;
        }
        data.isSaving = true;
        try {
            const result = await rpc('/provider/portal/trucks/deregistration/confirm', {
                truck_id: data.truck.id,
                code: data.code,
            });
            if (!result.success) {
                this.showNotification({ title: _t("Permanent deregistration was not completed"), message: result.error, type: 'danger' });
                return;
            }
            this.closeDeregistrationModals();
            this.showNotification({ title: _t("Unit permanently deregistered"), message: _t("The unit is no longer assignable and is hidden from the default list."), type: 'success' });
            await this.loadTrucks();
        } catch (error) {
            this.showNotification({ title: _t('Error'), message: error?.data?.message || error.message, type: 'danger' });
        } finally {
            data.isSaving = false;
        }
    }

    async cancelDeregistrationRequest() {
        const data = this.state.deregistration;
        const result = await rpc('/provider/portal/trucks/deregistration/cancel', { truck_id: data.truck.id });
        if (!result.success) {
            this.showNotification({ title: _t('Error'), message: result.error, type: 'danger' });
            return;
        }
        this.closeDeregistrationModals();
        this.showNotification({ title: _t("Cancelled"), message: _t("Permanent deregistration request was cancelled."), type: 'info' });
    }

    async openVehicleStatusConfirmation(truck) {
        if (!this.canEditVehicleStatus(truck)) {
            return;
        }
        const newState = truck.x_vehicle_service_state === 'available' ? 'not_available' : 'available';
        if (newState === 'not_available') {
            const reasonResult = await rpc('/provider/portal/trucks/not_available_reasons');
            if (!reasonResult.success) {
                this.showNotification({ title: _t('Error'), message: reasonResult.error, type: 'danger' });
                return;
            }
            this.state.temporaryDowntime = {
                show: true,
                truck,
                reason: '',
                reasons: reasonResult.reasons,
                returnDate: '',
                isSaving: false,
            };
            return;
        }
        const targetLabel = this.vehicleStatusLabel(newState);
        this.dialog.add(ConfirmationDialog, {
            title: _t('Change Unit Status'),
            body: _t('Do you want to change the unit status to %s?', targetLabel),
            confirm: () => this.updateVehicleStatus(truck.id, newState),
            cancel: () => {},
        });
    }

    async updateVehicleStatus(truckId, newState) {
        this.state.updatingTruckId = truckId;
        try {
            const result = await rpc('/provider/portal/trucks/update_status', {
                truck_id: truckId,
                new_state: newState,
            });
            if (!result.success) {
                this.showNotification({ title: _t('Error'), message: _t(result.error), type: 'danger' });
                return;
            }
            this.showNotification({ title: _t('Updated'), message: _t('Unit status updated.'), type: 'success' });
            await this.loadTrucks();
        } catch (err) {
            this.showNotification({ title: _t('Error'), message: _t(err?.data?.message || err.message), type: 'danger' });
        } finally {
            this.state.updatingTruckId = null;
        }
    }

    async saveTemporaryDowntime() {
        const data = this.state.temporaryDowntime;
        if (!data.reason || !data.returnDate) {
            this.showNotification({ title: _t("Required information"), message: _t("Enter a reason and estimated return date."), type: 'warning' });
            return;
        }
        data.isSaving = true;
        const result = await rpc('/provider/portal/trucks/update_status', {
            truck_id: data.truck.id, new_state: 'not_available',
            temporary_reason: data.reason, estimated_return_date: data.returnDate,
        });
        data.isSaving = false;
        if (!result.success) {
            this.showNotification({ title: _t('Error'), message: result.error, type: 'danger' });
            return;
        }
        data.show = false;
        await this.loadTrucks();
        this.showNotification({ title: _t('Updated'), message: _t('Unit status updated.'), type: 'success' });
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

    // Clicking a card filters by its state; clicking it again (or Total) clears it.
    selectVehicleState(vehicleState) {
        this.updateFilter('vehicle_state', this.state.filters.vehicle_state === vehicleState ? "" : vehicleState);
    }

    updateFilter(field, value) {
        this.state.filters[field] = value;
        this.pagination.reset();
    }

    async checkUserPermissions() {
        try {
            const [driverResult, statusResult, canPermanentlyDeregister] = await Promise.all([
                rpc('/provider/portal/trucks/can_add_driver'),
                rpc('/provider/portal/trucks/can_edit_status'),
                user.hasGroup('ike_event_portal.custom_group_portal_admin'),
            ]);
            this.state.canAddDriver = driverResult.can_edit;
            this.state.canEditUnitStatus = statusResult.can_edit;
            this.state.canPermanentlyDeregister = canPermanentlyDeregister;
        } catch (err) {
            this.showNotification({ title: _t("Error checking permissions"), message: _t(err?.data?.message || err.message || "An error occurred while checking user permissions."), type: 'danger' });
            this.state.canAddDriver = false;
            this.state.canEditUnitStatus = false;
            this.state.canPermanentlyDeregister = false;
        }
    }
}

registry.category("public_components").add("ike_event_portal.TrucksComponent", TrucksComponent);
