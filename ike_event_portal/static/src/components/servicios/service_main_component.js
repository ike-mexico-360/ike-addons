import { Component, onWillStart, useState, useRef, useEffect, onMounted, onWillUnmount } from "@odoo/owl";
import { useService, useBus } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { rpc } from "@web/core/network/rpc";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
// Import pagination - use the @module_name path
import { usePagination } from "../pagination/pagination_service";
import { PaginationComponent } from "../pagination/pagination_component";
import { CancelServiceDialog } from "../dialogs/cancel_service_dialog";

const IKE_SUPPLIER_CHANNEL = "ike_channel_supplier_";

export class ServicesMainComponent extends Component {
    static template = "ike_event_portal.ServicesMainComponent";
    static components = { PaginationComponent, CancelServiceDialog };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.busService = this.env.services.bus_service;
        this.user = user;
        this.supplier_id = 0;
        this.summaryRef = useRef("summaryContainer");
        this.trackingRef = useRef("trackingContainer");
        this.refreshInterval = null;
        this.notificationTimeout = null;
        this.state = useState({
            isCreating: false,
            selectedServiceId: null,
            services: [],
            isLoading: false,
            error: null,
            notification: null,
            showServiceSummaryModal: false,
            filters: {
                record: '',
                from: '',
                to: '',
                service: '',
                subservice: '',
            },
            serviceCostsData: null,
            isLoadingCosts: false,
            availableProducts: [],
            isAddingConcept: false,
            newConcept: {
                product_id: null,
                estimated_quantity: 1,
                quantity: 1,
                is_net: false,
            },
            currentEventId: null,
            currentSupplierId: null,
        });
        // Initialize pagination service
        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredServices,
        });
        onWillStart(async () => {
            await this.getSupplierId();
            await this.loadServices();
            await this.subscribeToEventSupplierNotification();
        });
        onMounted(() => {
            if (this.supplier_id) {
                this.subscribeToChannel();
            }
        });
        useEffect(
            () => {
                if (this.summaryRef.el && this.state.event_supplier_summary_data) {
                    this.summaryRef.el.innerHTML = this.state.event_supplier_summary_data;
                }
            },
            () => [this.state.showServiceSummaryModal, this.state.event_supplier_summary_data]
        );
        onWillUnmount(() => {
            if (this.notificationTimeout) {
                clearTimeout(this.notificationTimeout);
                this.notificationTimeout = null;
            }
        });
    }

    async loadConceptsByEventSupplierId(event_id, supplier_id) {
        return await this.orm.searchRead(
            'ike.event.supplier.product',
            [
                ['event_id', '=', event_id],
                ['supplier_id', '=', supplier_id],
                ['display_type', 'not in', ['line_section', 'line_note']]
            ],
            []
        );
    }

    async loadServices(isLoading = true) {
        this.state.isLoading = isLoading;
        this.state.error = null;
        try {
            const supplier_events = await this.getSupplierNotifiedEvents();
            this.state.services = supplier_events;

        } catch (err) {
            console.error("Error loading services:", err);
            this.state.error = "Failed to load services.";
        } finally {
            this.state.isLoading = false;
        }
    }

    subscribeToChannel() {
        const channel_name = IKE_SUPPLIER_CHANNEL + this.supplier_id;
        this.busService.addChannel(channel_name);
        console.log("Subscribed to channel:", channel_name);
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
                this.showNotification({ type: 'warning', message: 'El usuario no está asociado a ningún proveedor.' });
                return;
            }
            this.supplier_id = supplier.supplier_id[0];
        }
        catch (e) {
            this.showNotification({ type: 'error', message: 'Error al obtener el proveedor asociado.' });
        }

    }

    closeNotification() {
        if (this.notificationTimeout) {
            clearTimeout(this.notificationTimeout);
            this.notificationTimeout = null;
        }
        this.state.notification = null;
    }

    showNotification(notification) {
        // Clear existing timeout
        if (this.notificationTimeout) {
            clearTimeout(this.notificationTimeout);
        }

        // Set notification
        this.state.notification = notification;

        // Auto-dismiss after 5 seconds
        this.notificationTimeout = setTimeout(() => {
            this.state.notification = null;
            this.notificationTimeout = null;
        }, 5000);
    }

    subscribeToEventSupplierNotification() {
        this.busService.subscribe('ike_supplier_lines_reload_2', async (payload) => {
            console.log("Received notification:", payload);


            let ike_event_supplier = await this.getEventSupplierById(payload.data[0].id);
            let service_supplier_state = payload.data[0].state;
                if (ike_event_supplier && (service_supplier_state === 'notified' || service_supplier_state === 'assigned' || service_supplier_state === 'accepted')) {
                    let event = await this.getEventById(ike_event_supplier.event_id);
                    this.removeServiceById(ike_event_supplier.event_supplier_id);
                    this.fetchAndAppendService(ike_event_supplier, event)
                }
                if (ike_event_supplier && (service_supplier_state === 'timeout' || service_supplier_state === 'rejected')) {
                    if (ike_event_supplier.supplier_id == this.supplier_id) {
                        this.removeServiceById(ike_event_supplier.event_supplier_id);
                        this.showNotification({
                            message: 'El servicio ha sido actualizado y removido de la lista',
                            type: 'info'
                        });
                    }
                }

                // Handle cancel_event: remove from list and notify
                if (service_supplier_state === 'cancel_event') {
                const cancelData = payload.data[0];
                    const eventSupplierId = cancelData.id;
                    const cancelReason = cancelData.cancel_reason || '';
                    const cancelUser = cancelData.cancel_user || 'Administrador';

                    const index = this.state.services.findIndex(
                        service => service.event_supplier_id === eventSupplierId
                    );

                    if (index !== -1) {
                        this.state.services.splice(index, 1);
                        this.showNotification({
                            message: `El servicio ha sido cancelado por ${cancelUser}. Motivo: ${cancelReason}`,
                            type: 'warning',
                        });
                    }
                    return;
            }
        });
    }

    async loadNotificationService() {
        this.showNotification({
            message: ' tienes un nuevo servicio disponible: ',
            type: 'info', // info, success, warning, danger
        });
    }

    async fetchAndAppendService(event_supplier, event) {
        try {
            console.log("Appending new service to the list:", event_supplier, event);
            this.state.services.unshift({
                name: event.name,
                event_date: formatDateTime(deserializeDateTime(event.event_date), { format: "dd/MM/yyyy HH:mm:ss" }),
                location_label: this.sanitizeHtml(event.location_label),
                service_id: event.service_id[1],
                sub_service_id: event.sub_service_id[1],
                stage_id: event.stage_id[1],
                stage_id_label: event.stage_id_label,
                event_id: event_supplier.event_id,
                event_supplier_id: event_supplier.event_supplier_id,
                truck_id: event_supplier.truck_id,
                driver_name: event_supplier.driver_name,
                truck_name: event_supplier.truck_name,
                event_supplier_state: event_supplier.event_supplier_state,
                event_supplier_state_label: event_supplier.event_supplier_state_label,
                stage: event.stage_ref,
                highlighted: true,
            });

        } catch (err) {
            console.error(`Error fetching service ${eventId}:`, err);
        }
    }

    async notifyService(event_supplier_id) {
        try {
            let event_supplier = await this.GetSupplierNotifiedSingleEvent(event_supplier_id);
            if (event_supplier) {
                await this.orm.call(
                    'ike.event.supplier.public',
                    'action_notify_operator',
                    [event_supplier_id]
                );
                const [notification_sent_to_app] = await this.orm.searchRead(
                    'ike.event.supplier.public',
                    [
                        ['id', '=', event_supplier_id]
                    ],
                    ['notification_sent_to_app']
                );
                if (notification_sent_to_app) {
                    this.showNotification({
                        message: 'Notificación enviada exitosamente',
                        type: 'success',
                    });
                }
                // Refresh only the notified service instead of reloading the full list
                await this.refreshSingleService(event_supplier_id);
            }
            else {
                alert("Este servicio ya no se encuentra disponible para su aceptación");
            }

        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al aceptar el servicio: ' + message,
                    type: 'warning', // info, success, warning, danger
                });
                return;
            }
            this.showNotification({
                message: 'Error al notificar el servicio: ',
                type: 'danger',
            });
            console.error("Error notifying service:", err);
        }
    }

    async acceptService(event_supplier_id) {
        try {
            let event_supplier = await this.GetSupplierNotifiedSingleEvent(event_supplier_id);
            if (event_supplier) {

                await this.orm.call(
                    'ike.event.supplier.public',
                    'action_accept',
                    [event_supplier_id]
                );
                // Refresh only the accepted service instead of reloading the full list
                await this.refreshSingleService(event_supplier_id);
            }
            else {
                alert("Este servicio ya no se encuentra disponible para su aceptación");
            }

        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al aceptar el servicio: ' + message,
                    type: 'warning', // info, success, warning, danger
                });
                return;
            }
            this.showNotification({
                message: 'Error al aceptar el servicio',
                type: 'danger', // info, success, warning, danger
            });
            console.error("Error accepting service:", err);
        }
    }

    async refreshSingleService(event_supplier_id) {
        /**
         * Fetch the latest data for a single service and update it in-place
         * in the local state array, avoiding a full list reload.
         */
        try {
            const updated = await this.getEventSupplierById(event_supplier_id);
            if (!updated) {
                // Service no longer exists or is in an invalid state — remove it locally
                this.removeServiceById(event_supplier_id);
                return;
            }
            const index = this.state.services.findIndex(
                s => s.event_supplier_id === event_supplier_id
            );
            if (index !== -1) {
                // Patch only the fields that can change after an action
                Object.assign(this.state.services[index], {
                    event_supplier_state: updated.event_supplier_state,
                    event_supplier_state_label: updated.event_supplier_state_label,
                    truck_name: updated.truck_name,
                    driver_name: updated.driver_name,
                    highlighted: false,
                });
            }
        } catch (err) {
            console.error("Error refreshing single service:", err);
            // Fallback: reload the full list if single refresh fails
            await this.loadServices();
        }
    }

    onAcceptClick(event_supplier_id) {
        this.dialog.add(ConfirmationDialog, {
            title: "Confirmar Aceptación",
            body: "¿Estás seguro de que deseas aceptar este servicio?",
            confirm: async () => {
                await this.acceptService(event_supplier_id);
            },
            cancel: () => {

            },
        });
    }

    onAcceptNotify(event_supplier_id) {
        this.dialog.add(ConfirmationDialog, {
            title: "Confirmar Notificación",
            body: "¿Estás seguro de que deseas notificar este servicio?",
            confirm: async () => {
                await this.notifyService(event_supplier_id);
            },
            cancel: () => {

            },
        });
    }

    onCancelService(event_supplier_id) {
        this.dialog.add(CancelServiceDialog, {
            title: "Cancelar Servicio",
            onConfirm: async (cancelData) => {
                try {
                    let event_supplier = await this.GetSupplierNotifiedSingleEvent(event_supplier_id);
                    console.log("Event supplier for cancellation:", event_supplier);

                    if (event_supplier) {
                        const result = await rpc('/provider/portal/services/supplier_cancel', {
                            event_supplier_id: event_supplier_id,
                            cancel_reason_id: cancelData.cancel_reason_id,
                            reason_text: cancelData.reasonText
                        });

                        if (result.success) {
                            this.showNotification({
                                message: 'Servicio cancelado exitosamente',
                                type: 'info',
                            });
                            await this.loadServices();
                        } else {
                            this.showNotification({
                                message: result.error || 'Error al cancelar el servicio',
                                type: 'danger',
                            });
                        }
                    } else {
                        this.showNotification({
                            message: 'Este servicio ya no se encuentra disponible para su cancelación',
                            type: 'warning',
                        });
                    }
                } catch (err) {
                    if (err.data?.name === "odoo.exceptions.ValidationError") {
                        const message = err.data.message;
                        this.showNotification({
                            message: 'Error al cancelar el servicio: ' + message,
                            type: 'warning',
                        });
                        return;
                    }
                    console.error("Error cancelling service:", err);
                    this.showNotification({
                        message: 'Error al cancelar el servicio',
                        type: 'danger',
                    });
                }
            },
        });

    }

    async onRejectClick(event_supplier_id) {
        try {
            this.dialog.add(ConfirmationDialog, {
                title: "Confirmar Rechazo",
                body: "¿Estás seguro de que deseas rechazar este servicio?",
                confirm: async () => {
                    let event_supplier = await this.GetSupplierNotifiedSingleEvent(event_supplier_id);
                    if (event_supplier) {
                        await this.orm.call(
                            'ike.event.supplier',
                            'action_reject',
                            [event_supplier_id]
                        );
                        await this.loadServices();
                    }
                    else {
                        alert("Este servicio ya no se encuentra disponible para su aceptación");
                    }
                },
                cancel: () => {

                },
            });
        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al aceptar el servicio: ' + message,
                    type: 'warning', // info, success, warning, danger
                });
                return;
            }
        }
    }

    async onNotifyUser(event_supplier_id, event) {
        const truck_id = await this.getTruckById(event_supplier_id.truck_id[0]);
        if (!truck_id.driver_id) {
            console.error("Error sending notification: Not driver");
            this.showNotification({
                message: 'Error al enviar la notificación. El vehículo no tiene conductor.',
                type: 'danger'
            });
            return false;
        }
        const user = await this.getUserByPartner(truck_id.driver_id.id);

        try {
            const result = await rpc('/provider/portal/services/send_notification', {
                user_id: user.id,
                vehicle_id: truck_id.id,
                event_data: {
                    service_id: event.id.toString(),
                    ca_id: truck_id.x_center_id.id.toString(),
                    lng: event.location_longitude,
                    lat: event.location_latitude,
                    dst_lng: event.destination_longitude,
                    dst_lat: event.destination_latitude,
                    control: "1",
                    assignation_type: event_supplier_id.assignation_type,
                    estatus: event_supplier_id.state,
                    event_supplier_id: event_supplier_id.id,
                    user_code: event.user_code
                }
            });

            if (result.success) {
                console.log("Notification sent successfully");
                this.showNotification({
                    message: 'Notificación enviada exitosamente',
                    type: 'success'
                });
                return true;
            } else {
                console.error("Failed to send notification:", result.error);
                this.showNotification({
                    message: 'Error al enviar la notificación',
                    type: 'danger'
                });
            }
            return false;

        } catch (err) {
            console.error("Error sending notification:", err);
            this.showNotification({
                message: 'Error al enviar la notificación',
                type: 'danger'
            });
            return false;
        }
    }

    async GetSupplierNotifiedSingleEvent(event_supplier_id) {
        try {
            const [supplierLine] = await this.orm.searchRead(
                'ike.event.supplier.public',
                [
                    ['id', '=', event_supplier_id],
                    ['state', 'in', ['notified', 'accepted', 'assigned']]
                ],
                []
            );
            return supplierLine;
        } catch (err) {
            console.error("Error fetching supplier notified single event:", err);
            return null;
        }
    }

    async getSupplierNotifiedEvents() {
        try {
            const result = await rpc('/provider/portal/services/supplier_current_notified', {
                supplier_id: this.supplier_id
            });
            console.log("Supplier notified events result:", result);
            if (result.success) {
                return result.suppliers_events.map(supplier_event => ({
                    name: supplier_event.event_name,
                    event_date: supplier_event.event_date
                        ? formatDateTime(deserializeDateTime(supplier_event.event_date), { format: "dd/MM/yyyy HH:mm:ss" })
                        : "",
                    location_label: this.sanitizeHtml(supplier_event.location_label),
                    service_id: supplier_event.service_id_label,
                    sub_service_id: supplier_event.sub_service_id_label,
                    stage_id: supplier_event.stage_id,
                    stage_id_label: supplier_event.stage_id_label,
                    event_id: supplier_event.event_id,
                    event_supplier_id: supplier_event.event_supplier_id,
                    truck_id: supplier_event.truck_id,
                    driver_name: supplier_event.driver_name,
                    truck_name: supplier_event.truck_name,
                    event_supplier_state: supplier_event.event_supplier_state,
                    event_supplier_state_label: supplier_event.event_supplier_state_label,
                    stage: supplier_event.stage,
                }));
            } else {
                console.log(result.message);
                return [];
            }
        } catch (err) {
            console.error('Error getting current notified supplier:', err);
            return [];
        }
    }

    async getEventSupplierById(supplierLineId) {
        /**
         * Retrieve a single ike.event.supplier record by its ID using the backend endpoint
         * @param {number} supplierLineId - The ID of the ike.event.supplier record
         * @returns {object|null} - The supplier line record or null
         */
        try {
            const result = await rpc('/provider/portal/services/supplier_notified_single', {
                event_supplier_id: supplierLineId
            });

            if (result.success && result.supplier_event) {
                console.log('Event supplier found:', result.supplier_event);
                return result.supplier_event;
            } else {
                console.log('No event supplier found with ID:', supplierLineId, result.error);
                return null;
            }
        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al aceptar el servicio: ' + message,
                    type: 'warning', // info, success, warning, danger
                });
                return;
            }
        }
    }

    async getEventById(eventId) {
        /**
         * Retrieve all details of an ike.event record by its ID
         * @param {number} eventId - The ID of the ike.event record
         * @returns {object|null} - The event record with all details or null
         */
        try {
            const userLang = this.user.lang || 'es_MX';
            const [event] = await this.orm.read(
                'ike.event.public',
                [eventId],
                []
            );

            if (event) {
                if (event.sub_service_id && event.sub_service_id[0]) {
                    const [product] = await this.orm.read(
                        'product.product',
                        [event.sub_service_id[0]],
                        ['name']
                    );
                    if (event.stage_id && event.stage_id[0]) {
                        const [stage] = await this.orm.read(
                            'ike.event.stage',
                            [event.stage_id[0]],
                            ['name'],
                            { context: { lang: userLang } }
                        );
                        event.stage_id_label = stage.name;
                    }
                    event.sub_service_id = [product.id, product.name];
                }
                return event;
            } else {
                return null;
            }
        } catch (error) {
            return null;
        }
    }

    async getTruckById(truckId) {
        /**
         * Retrieve all details of an ike.event record by its ID
         * @param {number} truckId - The ID of the fleet.vehicle record
         * @returns {object|null} - The event record with all details or null
         */
        try {
            const driver = await this.orm.webSearchRead(
                'fleet.vehicle',
                [["id", "=", truckId]],
                {
                    specification: {
                        driver_id: {
                            fields: {
                                id: {},
                                display_name: {},
                            }
                        },
                        x_center_id: {
                            fields: {
                                id: {},
                                display_name: {},
                            }
                        }
                    }
                }
            );

            if (driver.records.length > 0) {
                return driver.records[0];
            } else {
                return null;
            }
        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al aceptar el servicio: ' + message,
                    type: 'warning', // info, success, warning, danger
                });
                return;
            }
        }
    }

    async getUserByPartner(partnerId) {
        /**
         * Retrieve all details of an ike.event record by its ID
         * @param {number} partnerId - The ID of the res.partner record
         * @returns {object|null} - The event record with all details or null
         */
        try {
            const user = await this.orm.webSearchRead(
                'res.users',
                [["partner_id", "=", partnerId]],
                {
                    specification: {
                        id: {},
                        display_name: {},
                    }
                }
            );

            if (user.records.length > 0) {
                return user.records[0];
            } else {
                return null;
            }
        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al aceptar el servicio: ' + message,
                    type: 'warning', // info, success, warning, danger
                });
                return;
            }
            console.error('Error retrieving user:', err);
            return null;
        }
    }

    async openServiceSummaryModal(event_supplier_id) {
        try {
            let event_supplier = await this.getEventSupplierById(event_supplier_id);
            this.state.showServiceSummaryModal = true;
            this.state.event_supplier_summary_data = event_supplier.event_supplier_summary_data;
            this.state.travel_tracking_url = event_supplier.travel_tracking_url;

            this.state.isLoadingCosts = true;
            this.state.serviceCostsData = null;
            console.log("Loading service costs data for event_supplier_id:", event_supplier.supplier_id, event_supplier.event_id);
            const rawCostsData = await this.loadConceptsByEventSupplierId(event_supplier.event_id, event_supplier.supplier_id);
            this.state.serviceCostsData = this.transformCostsData(rawCostsData);
            console.log("Service costs data loaded:", this.state.serviceCostsData);

            await this.loadAvailableProducts(event_supplier.event_id, event_supplier.supplier_id);
        }
        catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al cargar el resumen del servicio: ' + message,
                    type: 'warning', // info, success, warning, danger
                });
                return;
            }
            console.error("Error opening service summary modal:", err);
            this.showNotification({
                message: 'Error al cargar el resumen del servicio',
                type: 'danger'
            });
            this.state.serviceCostsData = null;
        }
        finally {
            this.state.isLoadingCosts = false;
        }

    }

    closeServiceSummaryModal() {
        this.state.showServiceSummaryModal = false;
        this.state.event_supplier_summary_data = null;
        this.state.travel_tracking_url = null;
        this.state.serviceCostsData = null;
        this.state.isLoadingCosts = false;
        this.state.isAddingConcept = false;
        this.state.availableProducts = [];
        this.state.newConcept = {
            product_id: null,
            estimated_quantity: 1,
            quantity: 1,
            is_net: false,
        };
        this.state.currentEventId = null;
        this.state.currentSupplierId = null;
    }

    sanitizeHtml(htmlString) {
        if (!htmlString) return '';
        const temp = document.createElement('div');
        temp.innerHTML = htmlString;
        return temp.textContent || temp.innerText || '';
    }

    onAddConceptClick() {
        /**
         * Show the new concept row in the table
         */
        this.state.isAddingConcept = true;
        this.state.newConcept = {
            product_id: null,
            estimated_quantity: 1,
            quantity: 1,
            is_net: false,
        };
    }

    onCancelAddConcept() {
        /**
         * Cancel adding a new concept
         */
        this.state.isAddingConcept = false;
        this.state.newConcept = {
            product_id: null,
            estimated_quantity: 1,
            quantity: 1,
            is_net: false,
        };
    }

    onNewConceptProductChange(ev) {
        console.log("Selected product ID:", ev);
        const productId = parseInt(ev.target.value, 10);
        this.state.newConcept.product_id = productId || null;
    }

    onNewConceptQuantityChange(field, ev) {
        const value = parseFloat(ev.target.value) || 0;
        this.state.newConcept[field] = value;
    }

    onNewConceptNetChange(ev) {
        this.state.newConcept.is_net = ev.target.checked;
    }

    async onCostItemFieldChange(itemId, field, ev) {
        /**
         * Handle changes to quantity or unit_price fields in the costs table
         * Updates the backend and refreshes the calculated fields
         */
        const value = parseFloat(ev.target.value) || 0;
        
        try {
            // Update the record in the backend
            await this.orm.write('ike.event.supplier.product', [itemId], {
                [field]: value
            });

            // Reload the costs data to get recalculated values
            const rawCostsData = await this.loadConceptsByEventSupplierId(
                this.state.currentEventId,
                this.state.currentSupplierId
            );
            this.state.serviceCostsData = this.transformCostsData(rawCostsData);

        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al actualizar: ' + message,
                    type: 'warning',
                });
                return;
            }
            console.error("Error updating cost item:", err);
            this.showNotification({
                message: 'Error al actualizar el concepto',
                type: 'danger',
            });
        }
    }

    async onSendAdditionalConceptsRequest() {
        /**
         * Send a request for additional concepts
         */
        try {
            // TODO: Implement the backend call to send the request
            this.showNotification({
                message: 'Solicitud de conceptos adicionales enviada exitosamente',
                type: 'success',
            });
        } catch (err) {
            console.error("Error sending additional concepts request:", err);
            this.showNotification({
                message: 'Error al enviar la solicitud',
                type: 'danger',
            });
        }
    }

    async onSaveNewConcept() {
        /**
         * Save the new concept to the database using backend endpoint
         * that applies onchange logic for pricing
         */
        if (!this.state.newConcept.product_id) {
            this.showNotification({
                message: 'Por favor seleccione un concepto',
                type: 'warning',
            });
            return;
        }

        try {
            // Call backend endpoint to create concept with proper pricing
            const result = await rpc('/provider/portal/services/create_concept', {
                event_id: this.state.currentEventId,
                supplier_id: this.state.currentSupplierId,
                product_id: this.state.newConcept.product_id,
                quantity: this.state.newConcept.quantity,
            });

            if (!result.success) {
                this.showNotification({
                    message: result.error || 'Error al agregar el concepto',
                    type: 'warning',
                });
                return;
            }

            this.showNotification({
                message: 'Concepto agregado exitosamente',
                type: 'success',
            });

            // Reload the costs data
            const rawCostsData = await this.loadConceptsByEventSupplierId(
                this.state.currentEventId,
                this.state.currentSupplierId
            );
            this.state.serviceCostsData = this.transformCostsData(rawCostsData);

            // Reload available products (to exclude the newly added one)
            await this.loadAvailableProducts(this.state.currentEventId, this.state.currentSupplierId);

            // Reset the adding state
            this.state.isAddingConcept = false;
            this.state.newConcept = {
                product_id: null,
                estimated_quantity: 1,
                quantity: 1,
                is_net: false,
            };

        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al agregar el concepto: ' + message,
                    type: 'warning',
                });
                return;
            }
            console.error("Error saving new concept:", err);
            this.showNotification({
                message: 'Error al agregar el concepto',
                type: 'danger',
            });
        }
    }

    removeServiceById(eventSupplierId) {
        /**
         * Remove a service from the state.services array by event_supplier_id
         * @param {number} eventSupplierId - The ID of the event supplier to remove
         */
        const index = this.state.services.findIndex(
            service => service.event_supplier_id === eventSupplierId
        );

        if (index !== -1) {
            this.state.services.splice(index, 1);
            console.log(`Service with event_supplier_id ${eventSupplierId} removed from list`);

            // Optionally show a notification

        } else {
            console.warn(`Service with event_supplier_id ${eventSupplierId} not found in list`);
        }
    }

    get filteredServices() {
        const { record, from, to, service, subservice } = this.state.filters;

        return this.state.services.filter(svc => {
            // Filter by expediente (partial match, case-insensitive)
            if (record) {
                const search = record.toLowerCase();
                const name = (svc.name || '').toLowerCase();
                if (!name.includes(search)) return false;
            }

            // Filter by fecha desde
            if (from && svc.event_date) {
                const serviceDate = this.parseServiceDate(svc.event_date);
                if (serviceDate && serviceDate < new Date(from)) return false;
            }

            // Filter by fecha hasta
            if (to && svc.event_date) {
                const serviceDate = this.parseServiceDate(svc.event_date);
                const hasta = new Date(to);
                hasta.setHours(23, 59, 59, 999);
                if (serviceDate && serviceDate > hasta) return false;
            }

            // Filter by servicio (exact match)
            if (service) {
                const raw = svc.service_id;
                const svcValue = (Array.isArray(raw) ? raw[1] : (raw || '')).toString().trim();
                if (svcValue !== service) return false;
            }

            // Filter by subservicio (exact match)
            if (subservice) {
                const raw = svc.sub_service_id;
                const sub = (Array.isArray(raw) ? raw[1] : (raw || '')).toString().trim();
                if (sub !== subservice) return false;
            }

            return true;
        });
    }

    get serviceOptions() {
        const values = this.state.services
            .map(s => {
                const val = s.service_id;
                return Array.isArray(val) ? val[1] : (val || '').toString().trim();
            })
            .filter(v => v);
        const uniqueValues = [...new Set(values)].sort();
        return uniqueValues;
    }

    get subserviceOptions() {
        const values = this.state.services
            .map(s => {
                const val = s.sub_service_id;
                return Array.isArray(val) ? val[1] : (val || '').toString().trim();
            })
            .filter(v => v);
        const uniqueValues = [...new Set(values)].sort();
        return uniqueValues;
    }

    parseServiceDate(dateStr) {
        if (!dateStr) return null;
        // Handle format "DD/MM/YYYY HH:MM:SS" or "DD/MM/YYYY"
        const parts = dateStr.split(' ');
        const dateParts = parts[0].split('/');
        if (dateParts.length === 3) {
            const [day, month, year] = dateParts;
            const timeParts = parts[1] ? parts[1].split(':') : ['0', '0', '0'];
            return new Date(year, month - 1, day, ...timeParts.map(Number));
        }
        // Fallback: try native parsing
        return new Date(dateStr);
    }

    onFilterChange(filterName, value) {
        this.state.filters[filterName] = value;
        this.pagination.reset(); // Reset to first page when filtering
    }

    clearFilters() {
        this.state.filters.record = '';
        this.state.filters.from = '';
        this.state.filters.to = '';
        this.state.filters.service = '';
        this.state.filters.subservice = '';
        this.pagination.reset(); // Reset to first page when clearing filters
    }

    transformCostsData(rawItems) {
        if (!rawItems || rawItems.length === 0) {
            return null;
        }

        const supplierName = rawItems[0].supplier_id ? rawItems[0].supplier_id[1] : "Sin proveedor";

        const items = rawItems.map((item, index) => ({
            id: item.id,
            row_number: index + 1,
            concept: item.product_id ? item.product_id[1] : "Sin concepto",
            quantity: item.quantity || 0,
            uom: item.uom_id ? item.uom_id[1] : "",
            unit_price: item.unit_price || 0,
            cost: item.cost_price || 0,
            iva: item.vat || 0,
            subtotal: item.subtotal || 0,
        }));

        const totalCost = items.reduce((sum, item) => sum + item.cost, 0);
        const totalIva = items.reduce((sum, item) => sum + item.iva, 0);
        const grandTotal = items.reduce((sum, item) => sum + item.subtotal, 0);

        return {
            supplier_name: supplierName,
            items: items,
            total_cost: this.formatCurrency(totalCost),
            total_iva: this.formatCurrency(totalIva),
            grand_total: this.formatCurrency(grandTotal),
        };
    }

    formatCurrency(value) {
        if (value === null || value === undefined) return "0.00";
        return value.toLocaleString('es-MX', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    async loadAvailableProducts(event_id, supplier_id) {
        /**
         * Load available products that can be added as concepts
         * Uses backend domain logic from get_concepts_domain()
         */
        try {
            this.state.currentEventId = event_id;
            this.state.currentSupplierId = supplier_id;

            // Call backend to get products with proper domain
            const result = await rpc('/provider/portal/services/get_available_concepts', {
                event_id: event_id,
                supplier_id: supplier_id
            });

            if (result.success) {
                this.state.availableProducts = result.products.map(product => ({
                    id: product.id,
                    name: product.name,
                    uom_id: product.uom_id,
                    uom_name: product.uom_id ? product.uom_id[1] : ''
                }));
                console.log("Available products loaded:", this.state.availableProducts);
            } else {
                console.error("Error loading products:", result.error);
                this.showNotification({
                    message: 'Error al cargar los conceptos: ' + (result.error || 'Error desconocido'),
                    type: 'warning',
                });
                this.state.availableProducts = [];
            }
        } catch (err) {
            if (err.data?.name === "odoo.exceptions.ValidationError") {
                const message = err.data.message;
                this.showNotification({
                    message: 'Error al cargar los conceptos disponibles: ' + message,
                    type: 'warning',
                });
                return;
            }
            console.error("Error loading available products:", err);
            this.state.availableProducts = [];
        }
    }

    // Use pagination.paginatedItems instead of filteredServices in template
    get paginatedServices() {
        return this.pagination.paginatedItems;
    }
}


registry.category("public_components").add("ike_event_portal.ServicesMainComponent", ServicesMainComponent);