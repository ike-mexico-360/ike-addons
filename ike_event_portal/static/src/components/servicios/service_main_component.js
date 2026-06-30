/** @odoo-module **/

import { Component, onWillStart, useState, useRef, useEffect, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { rpc } from "@web/core/network/rpc";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { usePagination } from "../pagination/pagination_service";
import { PaginationComponent } from "../pagination/pagination_component";
import { CancelServiceDialog } from "../dialogs/cancel_service_dialog";
// Sound notification sounds configuration
const NOTIFICATION_SOUNDS = {
    success: '/ike_event_portal/static/src/sounds/success.mp3',
    info: '/ike_event_portal/static/src/sounds/mixkit-correct-answer-tone-2870.wav',
    warning: '/ike_event_portal/static/src/sounds/warning.mp3',
    danger: '/ike_event_portal/static/src/sounds/error.mp3',
};

// Play sound notification
const playNotificationSound = (soundUrl) => {
    if (soundUrl) {
        try {
            const audio = new Audio(soundUrl);
            audio.volume = 0.7;
            audio.play().catch(err => console.warn('Audio play failed:', err));
        } catch (error) {
            console.error('Audio error:', error);
        }
    }
};

const IKE_SUPPLIER_CHANNEL = "ike_channel_supplier_";

export class ServicesMainComponent extends Component {
    static template = "ike_event_portal.ServicesMainComponent";
    static components = { PaginationComponent, CancelServiceDialog };
    translate(str) { return _t(str); }

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.busService = useService("bus_service");
        this.user = user;
        this.supplier_id = 0;
        this.summaryRef = useRef("summaryContainer");
        this.notification = useService("notification");
        this.state = useState({
            services: [],
            isLoading: false,
            error: null,
            filters: {
                record: '',
                from: '',
                to: '',
                service: '',
                subservice: '',
            },
            modal: {
                show: false,
                summaryData: null,
                travelTrackingUrl: null,
                costsData: null,
                isLoadingCosts: false,
                isAddingConcept: false,
                availableProducts: [],
                linkSupplierId: null,
                newConcept: { product_id: null, estimated_quantity: 1, quantity: 1, is_net: false },
                eventId: null,
                supplierId: null,
                eventSupplierId: null,
                stage: null,
                relojes: null,
                isLoadingRelojes: false,
            },
        });
        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredServices,
        });
        onWillStart(async () => {
            await this.getSupplierId();
            if (this.supplier_id) {
                await this.loadServices();
                await this.subscribeToEventSupplierNotification();
            }
        });
        onMounted(() => {
            if (this.supplier_id) {
                this.subscribeToChannel();
            }
        });
        useEffect(
            () => {
                if (this.summaryRef.el && this.state.modal.summaryData) {
                    this.summaryRef.el.innerHTML = this.state.modal.summaryData;
                }
            },
            () => [this.state.modal.show, this.state.modal.summaryData]
        );
    }

    async loadConceptsByEventSupplierId(supplier_link_id) {
        try {
            const result = await this.orm.webSearchRead(
                'ike.event.supplier.product',
                [
                    ['event_supplier_link_id', '=', supplier_link_id],
                    ['display_type', 'not in', ['line_section', 'line_note']],
                    ['parent_product_id', '=', false],
                ],
                {
                    specification: {
                        id: {},
                        supplier_id: {
                            fields: {
                                id: {},
                                name: {},
                            },
                        },
                        product_id: {
                            fields: {
                                id: {},
                                name: {},
                                display_name: {},
                            },
                        },
                        quantity: {},
                        uom_id: {
                            fields: {
                                id: {},
                                name: {},
                                display_name: {},
                            },
                        },
                        unit_price: {},
                        cost_price: {},
                        vat: {},
                        subtotal: {},
                        from_portal: {},
                    },
                    context: { lang: this.user.lang || 'es_MX' },
                }
            );
            return result.records;
        } catch (err) {
            this.showNotification({ title: _t("Error loading service concepts"), message: _t(err?.data?.message || err.message || "An unknown error occurred"), type: 'danger' });
            return [];
        }
    }

    async loadServices(isLoading = true) {
        this.state.isLoading = isLoading;
        try {
            this.state.services = await this.getSupplierNotifiedEvents();
        }
        finally {
            this.state.isLoading = false;
        }
    }

    subscribeToChannel() {
        this.busService.addChannel(IKE_SUPPLIER_CHANNEL + this.supplier_id);
    }

    async getSupplierId() {
        try {
            const result = await this.orm.webSearchRead(
                'res.partner.supplier_users.rel',
                [['user_id', '=', this.user.userId]],
                {
                    specification: {
                        supplier_id: {
                            fields: {
                                id: {},
                            },
                        },
                    },
                }
            );
            const [supplier] = result.records;
            if (!supplier) return;
            this.supplier_id = supplier.supplier_id.id;
        } catch (err) {
            this.showNotification({ title: _t("Error obtaining the associated provider"), message: _t(err?.data?.message || err.message || "An unknown error occurred"), type: 'danger' });
        }
    }

    showNotification({ message, type = 'info', sticky = true, title }) {
        this.notification.add(message, { type, sticky, title });
    }

    showNotificationWithSound({ message, type = 'info', sticky = true, title }) {
        const soundUrl = NOTIFICATION_SOUNDS[type] || null;
        playNotificationSound(soundUrl);
        this.notification.add(message, { type, sticky, title });
    }

    subscribeToEventSupplierNotification() {
        this.busService.subscribe('ike_supplier_lines_reload_2', async (payload) => {
            for (const item of payload.data) {
                await this._handleSupplierNotificationItem(item);
            }
        });
    }

    async _handleSupplierNotificationItem(item) {
        const ACTIVE_STATES = ['notified', 'assigned', 'accepted'];
        const REMOVED_STATES = ['timeout', 'rejected'];

        if (item.state === 'cancel_event') {
            this._handleCancelledService(item);
            return;
        }

        const event_supplier = await this.getEventSupplierById(item.id);
        if (!event_supplier) return;

        if (ACTIVE_STATES.includes(item.state)) {
            this.showNotification({ title: _t("Service Updated"), message: _t('You have a new service available.'), type: 'info' });
            this.skipSupplierFromEvent(event_supplier.event_id);
            await this._handleActiveService(event_supplier);
        } else if (REMOVED_STATES.includes(item.state) && event_supplier.supplier_id == this.supplier_id) {
            this._handleRemovedService(event_supplier);
        }
    }

    async _handleActiveService(event_supplier) {
        const event = await this.getEventById(event_supplier.event_id);
        this.fetchAndAppendService(event_supplier, event);
    }

    _handleRemovedService(event_supplier) {
        this.removeServiceById(event_supplier.event_supplier_id);
        this.showNotification({ title: _t("Service Updated"), message: _t('The service has been updated and removed from the list'), type: 'info' });
    }

    _handleCancelledService(item) {
        const index = this.state.services.findIndex(service => service.event_supplier_id === item.id);
        if (index === -1) return;
        this.state.services.splice(index, 1);
        this.showNotification({
            message: _t("The service has been cancelled by") + " " + (item.cancel_user || _t("Administrator")) + ". " + _t("Reason:") + " " + _t(item.cancel_reason || ""),
            type: 'warning',
            title: _t("Service Cancelled")
        });
    }

    async fetchAndAppendService(event_supplier, event) {
        try {
            this.state.services.unshift({
                name: event.name,
                event_date: formatDateTime(deserializeDateTime(event.event_date), { format: "dd/MM/yyyy HH:mm:ss" }),
                location_label: this.sanitizeHtml(event.location_label),
                service_id: event.service_id?.name,
                sub_service_id: event.sub_service_id?.name,
                stage_id: event.stage_id?.name,
                stage_id_label: event.stage_id?.name,
                event_id: event_supplier.event_id,
                event_supplier_id: event_supplier.event_supplier_id,
                truck_id: event_supplier.truck_id,
                driver_name: event_supplier.driver_name,
                truck_name: event_supplier.truck_name,
                event_supplier_state: event_supplier.event_supplier_state,
                event_supplier_state_label: event_supplier.event_supplier_state_label,
                stage: event_supplier.stage,
            });
        } catch (err) {
            this.showNotification({ title: _t("Error adding service"), message: _t(err?.data?.message || err.message || "An error occurred while adding the service to the list."), type: 'danger' });
        }
    }

    async notifyService(event_supplier_id) {
        try {
            const event_supplier = await this._requireNotifiedEvent(event_supplier_id, _t('This service is no longer available for acceptance.'));
            if (!event_supplier) return;
            await this.orm.call('ike.event.supplier.public', 'action_notify_operator', [event_supplier_id]);
            const { records: [result] } = await this.orm.webSearchRead(
                'ike.event.supplier.public',
                [['id', '=', event_supplier_id]],
                {
                    specification: {
                        notification_sent_to_app: {},
                    },
                }
            );
            if (result?.notification_sent_to_app) {
                this.showNotification({ title: _t("Notification Sent"), message: _t('Notification sent successfully'), type: 'success' });
            }
            await this.refreshSingleService(event_supplier_id);
        } catch (err) {
            this.showNotification({ title: _t("Error notifying service"), message: _t(err?.data?.message || err.message || "An error occurred while notifying the service."), type: 'danger' });
        }
    }

    async acceptService(event_supplier_id) {
        try {
            const event_supplier = await this._requireNotifiedEvent(event_supplier_id, _t('This service is no longer available for acceptance.'));
            if (!event_supplier) return;
            await this.orm.call('ike.event.supplier.public', 'action_accept', [event_supplier_id]);
            await this.refreshMultipleServices(event_supplier.event_id.id, event_supplier.supplier_id.id);
        } catch (err) {
            this.showNotification({ title: _t("Error accepting service"), message: _t(err?.data?.message || err.message || "An error occurred while accepting the service."), type: 'danger' });
        }
    }

    async refreshSingleService(event_supplier_id) {
        try {
            const updated = await this.getEventSupplierById(event_supplier_id);
            if (!updated) {
                this.removeServiceById(event_supplier_id);
                return;
            }
            const index = this.state.services.findIndex(s => s.event_supplier_id === event_supplier_id);
            if (index !== -1) {
                Object.assign(this.state.services[index], {
                    event_supplier_state: updated.event_supplier_state,
                    event_supplier_state_label: updated.event_supplier_state_label,
                    truck_name: updated.truck_name,
                    driver_name: updated.driver_name,
                    stage: updated.stage,
                    highlighted: false,
                });
            }
        } catch (err) {
            await this.loadServices();
        }
    }

    onAcceptClick(event_supplier_id) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirm Acceptance"),
            body: _t("Are you sure you want to accept this service?"),
            confirm: async () => await this.acceptService(event_supplier_id),
            cancel: () => { },
        });
    }

    onAcceptNotify(event_supplier_id) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirm Notification"),
            body: _t("Are you sure you want to notify this service?"),
            confirm: async () => await this.notifyService(event_supplier_id),
            cancel: () => { },
        });
    }

    onCancelService(event_supplier_id) {
        this.dialog.add(CancelServiceDialog, {
            title: _t("Cancel Service"),
            onConfirm: async (cancelData) => {
                const event_supplier = await this._requireNotifiedEvent(event_supplier_id, _t('This service is no longer available for cancellation.'));
                if (!event_supplier) return;
                const result = await rpc('/provider/portal/services/supplier_cancel', {
                    event_supplier_id: event_supplier_id,
                    cancel_reason_id: cancelData.cancel_reason_id,
                    reason_text: cancelData.reasonText,
                });
                if (result.success) {
                    this.showNotification({ title: _t("Service Cancelled"), message: _t("Service canceled successfully"), type: 'success' });
                    await this.loadServices();
                } else {
                    this.showNotification({ title: _t("Error canceling service"), message: _t(result.error || "An error occurred while canceling the service."), type: 'danger' });
                }
            },
        });
    }

    onRejectClick(event_supplier_id) {
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirm Rejection"),
            body: _t("Are you sure you want to reject this service?"),
            confirm: async () => {
                try {
                    const event_supplier = await this._requireNotifiedEvent(event_supplier_id, _t('This service is no longer available for rejection.'));
                    if (!event_supplier) return;
                    await this.orm.call('ike.event.supplier.public', 'action_reject', [event_supplier_id]);
                    await this.loadServices();
                } catch (err) {
                    this.showNotification({ title: _t("Error rejecting service"), message: _t(err?.data?.message || err.message || "An error occurred while rejecting the service."), type: 'danger' });
                }
            },
            cancel: () => { },
        });
    }

    async _requireNotifiedEvent(event_supplier_id, message) {
        const event_supplier = await this._getSupplierNotifiedSingleEvent(event_supplier_id);
        if (!event_supplier) {
            this.showNotification({ title: _t("Service Unavailable"), message: message, type: 'warning' });
            return null;
        }
        return event_supplier;
    }

    async _getSupplierNotifiedSingleEvent(event_supplier_id) {
        try {
            const result = await this.orm.webSearchRead(
                'ike.event.supplier.public',
                [['id', '=', event_supplier_id], ['state', 'in', ['notified', 'accepted', 'assigned']]],
                {
                    specification: {
                        id: {},
                        supplier_id: { fields: { id: {}, display_name: {} } },
                        event_id: { fields: { id: {}, display_name: {} } },
                    },
                }
            );
            return result.records[0] ?? null;
        } catch (err) {
            this.showNotification({ title: _t("Error loading supplier event"), message: _t(err?.data?.message || err.message || "An error occurred while loading the supplier event."), type: 'danger' });
            return null;
        }
    }

    async getSupplierNotifiedEvents() {
        try {
            const result = await rpc('/provider/portal/services/supplier_current_notified', { supplier_id: this.supplier_id });
            if (!result.success) {
                this.showNotification({ title: _t("Error loading notified events"), message: _t(result.error || "An error occurred while loading the notified events."), type: 'danger' });
                return [];
            }
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
                supplier_link_id: supplier_event.supplier_link_id,
            }));
        } catch (err) {
            this.showNotification({ title: _t("Error processing notified events"), message: _t(err?.data?.message || err.message || "An error occurred while processing the notified events."), type: 'danger' });
            return [];
        }
    }

    async getEventSupplierById(supplierLineId) {
        const result = await rpc('/provider/portal/services/supplier_notified_single', { event_supplier_id: supplierLineId });
        if (result.success && result.supplier_event) {
            return result.supplier_event;
        }
        this.showNotification({ title: _t("Error loading supplier event"), message: _t(result.error || "An error occurred while loading the supplier event."), type: 'danger' });
        return null;
    }

    async getEventById(eventId) {
        try {
            const userLang = this.user.lang || 'es_MX';
            const result = await this.orm.webSearchRead(
                'ike.event.public',
                [['id', '=', eventId]],
                {
                    specification: {
                        name: {},
                        event_date: {},
                        location_label: {},
                        service_id: {
                            fields: {
                                id: {},
                                name: {},
                            },
                        },
                        sub_service_id: {
                            fields: {
                                id: {},
                                name: {},
                            },
                        },
                        stage_id: {
                            fields: {
                                id: {},
                                name: {},
                            },
                        },
                    },
                    context: { lang: userLang },
                }
            );
            const [event] = result.records;
            return event ?? null;
        } catch (err) {
            this.showNotification({ title: _t("Error loading event"), message: _t(err?.data?.message || err.message || "An error occurred while loading the event."), type: 'danger' });
        }
    }

    get _defaultModalState() {
        return {
            show: false,
            summaryData: null,
            travelTrackingUrl: null,
            costsData: null,
            isLoadingCosts: false,
            isAddingConcept: false,
            availableProducts: [],
            linkSupplierId: null,
            newConcept: { product_id: null, estimated_quantity: 1, quantity: 1, is_net: false },
            eventId: null,
            supplierId: null,
            eventSupplierId: null,
            stage: null,
            relojes: null,
            isLoadingRelojes: false,
        };
    }

    async openServiceSummaryModal(event_supplier_id) {
        this.state.modal.show = true;
        this.state.modal.isLoadingCosts = true;
        this.state.modal.isLoadingRelojes = true;
        this.state.modal.costsData = null;
        this.state.modal.relojes = null;
        try {
            const event_supplier = await this.getEventSupplierById(event_supplier_id);
            if (!event_supplier) return;

            const { supplier_link_id, event_id, supplier_id } = event_supplier;
            this.state.modal.summaryData = event_supplier.event_supplier_summary_data;
            this.state.modal.travelTrackingUrl = event_supplier.travel_tracking_url;
            this.state.modal.eventSupplierId = event_supplier_id;
            this.state.modal.linkSupplierId = supplier_link_id;
            this.state.modal.stage = event_supplier.stage ?? null;

            const [rawCostsData] = await Promise.all([
                this.loadConceptsByEventSupplierId(supplier_link_id),
                this.loadRelojes(event_supplier_id),
            ]);
            this.state.modal.costsData = this.transformCostsData(rawCostsData);
            await this.loadAvailableProducts(event_id, supplier_id, supplier_link_id);
        } catch (err) {
            this.showNotification({ title: _t("Error loading service summary"), message: _t(err?.data?.message || err.message || "An error occurred while loading the service summary."), type: 'danger' });
            this.state.modal.costsData = null;
        } finally {
            this.state.modal.isLoadingCosts = false;
        }
    }

    async loadRelojes(event_supplier_id) {
        this.state.modal.isLoadingRelojes = true;
        try {
            const result = await rpc('/provider/portal/services/get_relojes', { event_supplier_id });
            if (result.success) {
                this.state.modal.relojes = this._formatRelojData(result.relojes);
            }
        } catch (err) {
            this.showNotification({ title: _t("Error loading clocks"), message: _t(err?.data?.message || err.message || "An error occurred"), type: 'danger' });
        } finally {
            this.state.modal.isLoadingRelojes = false;
        }
    }

    _formatRelojData(relojes) {
        const fmt = (dateStr) => {
            if (!dateStr) return null;
            try {
                return formatDateTime(deserializeDateTime(dateStr), { format: "dd/MM/yyyy HH:mm:ss" });
            } catch {
                return dateStr;
            }
        };
        return {
            arrived: { ...relojes.arrived, formatted_date: fmt(relojes.arrived?.date) },
            contacted: { ...relojes.contacted, formatted_date: fmt(relojes.contacted?.date) },
            finalized: { ...relojes.finalized, formatted_date: fmt(relojes.finalized?.date) },
        };
    }

    onStampRelojClick(stage) {
        const labels = { arrived: _t('Arrived'), contacted: _t('Contacted'), finalized: _t('Finalized') };
        this.dialog.add(ConfirmationDialog, {
            title: _t("Confirm Clock Registration"),
            body: _t("Are you sure you want to register the current time for the '%s' stage? This action cannot be undone.", labels[stage] || stage),
            confirm: async () => await this._stampReloj(stage),
            cancel: () => { },
        });
    }

    async _stampReloj(stage) {
        const eventSupplierId = this.state.modal.eventSupplierId;
        if (!eventSupplierId) return;
        try {
            const result = await rpc('/provider/portal/services/stamp_reloj', {
                event_supplier_id: eventSupplierId,
                stage,
            });
            if (result.success) {
                this.state.modal.relojes = this._formatRelojData(result.relojes);
                this.showNotification({ title: _t("Clock registered"), message: _t("The time has been registered successfully."), type: 'success' });
                if (stage === 'finalized') {
                    await this.loadServices(false);
                } else {
                    await this.refreshSingleService(eventSupplierId);
                }
            } else {
                this.showNotification({ title: _t("Error registering clock"), message: _t(result.error || "An error occurred"), type: 'danger' });
            }
        } catch (err) {
            this.showNotification({ title: _t("Error registering clock"), message: _t(err?.data?.message || err.message || "An error occurred"), type: 'danger' });
        }
    }

    closeServiceSummaryModal() {
        Object.assign(this.state.modal, this._defaultModalState);
    }

    sanitizeHtml(htmlString) {
        if (!htmlString) return '';
        const temp = document.createElement('div');
        temp.innerHTML = htmlString;
        return temp.textContent || temp.innerText || '';
    }

    get isEventFinalized() {
        return this.state.modal.stage === 'finalized';
    }

    onAddConceptClick() {
        if (this.isEventFinalized) return;
        this.state.modal.isAddingConcept = true;
        this.state.modal.newConcept = { product_id: null, estimated_quantity: 1, quantity: 1, is_net: false };
    }

    onCancelAddConcept() {
        this.state.modal.isAddingConcept = false;
        this.state.modal.newConcept = { product_id: null, estimated_quantity: 1, quantity: 1, is_net: false };
    }

    onNewConceptProductChange(ev) {
        this.state.modal.newConcept.product_id = parseInt(ev.target.value, 10) || null;
    }

    onNewConceptQuantityChange(field, ev) {
        this.state.modal.newConcept[field] = parseFloat(ev.target.value) || 0;
    }

    onNewConceptNetChange(ev) {
        this.state.modal.newConcept.is_net = ev.target.checked;
    }

    async onCostItemFieldChange(itemId, field, ev) {
        const value = parseFloat(ev.target.value) || 0;
        try {
            await this.orm.write('ike.event.supplier.product', [itemId], { [field]: value });
            const rawCostsData = await this.loadConceptsByEventSupplierId(this.state.modal.linkSupplierId);
            this.state.modal.costsData = this.transformCostsData(rawCostsData);
        } catch (err) {
            this.showNotification({ title: _t("Error updating concept"), message: _t((err?.data?.message || err.message || "An error occurred while updating the concept.")), type: 'danger' });
        }
    }

    async onSendAdditionalConceptsRequest() {
        try {
            const response = await rpc('/provider/portal/supplier/request_authorization', { event_supplier_id: this.state.modal.eventSupplierId });
            if (response.success) {
                this.showNotification({ title: _t("Authorization requested successfully"), message: _t("Your request has been submitted for review."), type: 'success' });
                return;
            }
            this.showNotification({ title: _t("Error requesting authorization"), message: _t(response.error || "An error occurred while requesting authorization."), type: 'danger' });
        } catch (err) {
            this.showNotification({ title: _t("Error requesting authorization"), message: _t(err?.data?.message || err.message || "An error occurred while requesting authorization."), type: 'danger' });
        }
    }

    async onSaveNewConcept() {
        if (!this.state.modal.newConcept.product_id) {
            this.showNotification({ title: _t("Please select a concept"), message: _t("A concept must be selected to save."), type: 'warning' });
            return;
        }
        const result = await rpc('/provider/portal/services/create_concept', {
            event_id: this.state.modal.eventId,
            supplier_id: this.state.modal.supplierId,
            product_id: this.state.modal.newConcept.product_id,
            quantity: this.state.modal.newConcept.quantity,
            supplier_link_id: this.state.modal.linkSupplierId,
        });
        if (!result.success) {
            this.showNotification({ title: _t("Error adding concept"), message: _t(result.error || "Error creating concept"), type: 'warning' });
            return;
        }
        this.showNotification({ title: _t("Concept added successfully"), message: _t("The concept has been added successfully."), type: 'success' });
        const rawCostsData = await this.loadConceptsByEventSupplierId(this.state.modal.linkSupplierId);
        this.state.modal.costsData = this.transformCostsData(rawCostsData);
        await this.loadAvailableProducts(this.state.modal.eventId, this.state.modal.supplierId, this.state.modal.linkSupplierId);
        this.state.modal.isAddingConcept = false;
        this.state.modal.newConcept = { product_id: null, estimated_quantity: 1, quantity: 1, is_net: false };
    }

    async onDeleteConcept(itemId) {
        this.dialog.add(ConfirmationDialog, {
            title: _t('Confirm Deletion'),
            body: _t('Are you sure you want to delete this concept?'),
            confirm: async () => {
                try {
                    const result = await rpc('/provider/portal/services/delete_concept', { concept_id: itemId });
                    if (!result.success) {
                        this.showNotification({ title: _t("Error deleting concept"), message: _t(result.error || "Error deleting concept"), type: 'warning' });
                        return;
                    }
                    const rawCostsData = await this.loadConceptsByEventSupplierId(this.state.modal.linkSupplierId);
                    this.state.modal.costsData = this.transformCostsData(rawCostsData);
                    await this.loadAvailableProducts(this.state.modal.eventId, this.state.modal.supplierId, this.state.modal.linkSupplierId);
                } catch (err) {
                    this.showNotification({ title: _t("Error deleting concept"), message: _t(err?.data?.message || err.message), type: 'danger' });
                }
            }
        });
    }

    removeServiceById(eventSupplierId) {
        const index = this.state.services.findIndex(service => service.event_supplier_id === eventSupplierId);
        if (index !== -1) {
            this.state.services.splice(index, 1);
        }
    }

    get filteredServices() {
        const { record, from, to, service, subservice } = this.state.filters;
        return this.state.services.filter(svc => {
            if (record && !(svc.name || '').toLowerCase().includes(record.toLowerCase())) return false;
            if (from && svc.event_date) {
                const serviceDate = this.parseServiceDate(svc.event_date);
                if (serviceDate && serviceDate < new Date(from)) return false;
            }
            if (to && svc.event_date) {
                const serviceDate = this.parseServiceDate(svc.event_date);
                const hasta = new Date(to);
                hasta.setHours(23, 59, 59, 999);
                if (serviceDate && serviceDate > hasta) return false;
            }
            if (service && (svc.service_id || '').toString().trim() !== service) return false;
            if (subservice && (svc.sub_service_id || '').toString().trim() !== subservice) return false;
            return true;
        });
    }

    get serviceOptions() {
        return [...new Set(this.state.services.map(s => (s.service_id || '').toString().trim()).filter(v => v))].sort();
    }

    get subserviceOptions() {
        return [...new Set(this.state.services.map(s => (s.sub_service_id || '').toString().trim()).filter(v => v))].sort();
    }

    parseServiceDate(dateStr) {
        if (!dateStr) return null;
        const parts = dateStr.split(' ');
        const dateParts = parts[0].split('/');
        if (dateParts.length === 3) {
            const [day, month, year] = dateParts;
            const timeParts = parts[1] ? parts[1].split(':') : ['0', '0', '0'];
            return new Date(year, month - 1, day, ...timeParts.map(Number));
        }
        return new Date(dateStr);
    }

    onFilterChange(filterName, value) {
        this.state.filters[filterName] = value;
        this.pagination.reset();
    }

    clearFilters() {
        this.state.filters.record = '';
        this.state.filters.from = '';
        this.state.filters.to = '';
        this.state.filters.service = '';
        this.state.filters.subservice = '';
        this.pagination.reset();
    }

    transformCostsData(rawItems) {
        if (!rawItems || rawItems.length === 0) return null;
        const supplierName = rawItems[0].supplier_id?.name ?? _t("Sin proveedor");
        const items = rawItems.filter(item => item.product_id?.name).map((item, index) => ({
            id: item.id,
            row_number: index + 1,
            concept: item.product_id.name,
            quantity: item.quantity || 0,
            uom: item.uom_id?.name ?? "",
            unit_price: item.unit_price || 0,
            cost: item.cost_price || 0,
            iva: item.vat || 0,
            subtotal: item.subtotal || 0,
            from_portal: item.from_portal || false,
        }));
        return {
            supplier_name: supplierName,
            items,
            total_cost: this.formatCurrency(items.reduce((sum, item) => sum + item.cost, 0)),
            total_iva: this.formatCurrency(items.reduce((sum, item) => sum + item.iva, 0)),
            grand_total: this.formatCurrency(items.reduce((sum, item) => sum + item.subtotal, 0)),
        };
    }

    formatCurrency(value) {
        if (value === null || value === undefined) return "0.00";
        return value.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    async loadAvailableProducts(event_id, supplier_id, supplier_link_id) {
        this.state.modal.eventId = event_id;
        this.state.modal.supplierId = supplier_id;
        try {
            const result = await rpc('/provider/portal/services/get_available_concepts', {
                event_id,
                supplier_id,
                supplier_link_id,
            });
            if (result.success) {
                this.state.modal.availableProducts = result.products.map(product => ({
                    id: product.id,
                    name: product.name,
                    uom_id: product.uom_id,
                    uom_name: product.uom_id ? product.uom_id[1] : '',
                }));
            } else {
                this.showNotification({ title: _t("Error loading available concepts"), message: _t(result.error) || "", type: 'warning' });
                this.state.modal.availableProducts = [];
            }
        } catch (err) {
            this.showNotification({ title: _t("Error loading available concepts"), message: _t(err?.data?.message || err.message), type: 'danger' });
            this.state.modal.availableProducts = [];
        }
    }

    skipSupplierFromEvent(event_id) {
        const toRemove = this.state.services.filter(s => s.event_id === event_id);
        toRemove.forEach(s => this.removeServiceById(s.event_supplier_id));
    }

    get paginatedServices() {
        return this.pagination.paginatedItems;
    }

    async refreshMultipleServices(event_id, supplier_id) {
        try {
            const supplierLines = await this.orm.searchRead(
                'ike.event.supplier.public',
                [
                    ['event_id', '=', event_id],
                    ['supplier_id', '=', supplier_id]
                ],
                []
            );

            // Index backend results by event_supplier_id for fast lookup
            const backendMap = new Map(supplierLines.map(l => [l.event_supplier_id, l]));
            console.log("Backend supplier lines for refresh:", supplierLines);
            // Iterate backwards so splicing doesn't skip elements
            for (let i = this.state.services.length - 1; i >= 0; i--) {
                const svc = this.state.services[i];
                if (svc.event_id !== event_id) continue;

                const backendLine = backendMap.get(svc.event_supplier_id);

                if (!backendLine || backendLine.event_supplier_state === 'notified') {
                    // No longer relevant (dismissed because another operator was accepted)
                    this.state.services.splice(i, 1);
                } else {
                    Object.assign(svc, {
                        event_supplier_state: backendLine.event_supplier_state,
                        event_supplier_state_label: backendLine.event_supplier_state_label,
                        truck_name: backendLine.truck_name,
                        driver_name: backendLine.driver_name,
                        stage: backendLine.stage,
                        highlighted: false,
                    });
                }
            }
        } catch (error) {
            this.showNotification({ title: _t("Error refreshing services"), message: _t(error?.data?.message || error.message || "An error occurred while refreshing the services."), type: 'danger' });
        }
    }
}

registry.category("public_components").add("ike_event_portal.ServicesMainComponent", ServicesMainComponent);
