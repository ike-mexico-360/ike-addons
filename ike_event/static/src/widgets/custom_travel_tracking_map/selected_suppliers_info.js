import { Component, markup, onWillStart, onWillUnmount, onWillUpdateProps, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class IkeSelectedSuppliersInfo extends Component {
    static template = "ike_event.IkeSelectedSuppliersInfo";
    static props = {
        ...standardFieldProps,
        resModel: { type: String, optional: true },
    };

    setup() {
        super.setup();
        this.orm = useService("orm");
        this.action = useService("action");
        this.busService = this.env.services.bus_service;
        this.isDestroyed = false;
        this.loadRequestId = 0;
        this.busChannel = null;

        this.state = useState({
            vehicleRecord: {},
            suppliers: [],
            locations: {},
            event_type_name: "",
        });

        onWillStart(async () => {
            this.subscribeToChannel(this.props.record.resId);
            await this.loadData();
        });

        onWillUnmount(() => {
            this.isDestroyed = true;
            this.unsubscribeFromChannel();
            this.state.suppliers = [];
        });

        onWillUpdateProps(async (nextProps) => {
            if (this.props.record.resId !== nextProps.record.resId) {
                this.unsubscribeFromChannel();
                this.subscribeToChannel(nextProps.record.resId);
                await this.loadData(nextProps);
            }
        });
    }

    subscribeToChannel(eventId) {
        if (!eventId) {
            return;
        }
        this.busChannel = `ike_channel_event_${eventId}`;
        this.busService.addChannel(this.busChannel);
        this.busService.subscribe("ike_event_supplier_reload", this.handleNotification);
    }

    unsubscribeFromChannel() {
        if (this.busChannel) {
            this.busService.deleteChannel(this.busChannel);
            this.busChannel = null;
        }
        this.busService.unsubscribe("ike_event_supplier_reload", this.handleNotification);
    }

    handleNotification = async (message) => {
        if (this.isDestroyed) {
            return;
        }

        // Si el backend manda event_id, mejor filtrar:
        if (message.event_id && message.event_id !== this.props.record.resId) {
            return;
        }

        try {
            await this.loadData();
        } catch (error) {
            if (!this.isDestroyed) {
                console.error("Error reloading supplier info:", error);
            }
        }

        if (!this.isDestroyed && message.state && message.state.includes("cancel")) {
            console.log(`Supplier ${message.id} was cancelled: ${message.cancel_reason || "No reason"}`);
        }
    };

    get stateLabels() {
        return {
            accepted: _t("Accepted"),
            cancel: _t("Cancelled"),
            cancel_event: _t("Cancelled by Event"),
            cancel_supplier: _t("Cancelled by Supplier"),
        };
    }

    getStateLabel(state) {
        return this.stateLabels[state] || state;
    }

    async loadData(props = null) {
        const currentRequestId = ++this.loadRequestId;
        const propsToUse = props || this.props;
        const values = propsToUse.record.data[propsToUse.name];

        if (!values || !values.resIds || values.resIds.length === 0) {
            if (!this.isDestroyed && currentRequestId === this.loadRequestId) {
                this.state.suppliers = [];
            }
            return;
        }

        const { service_res_model, service_res_id } = propsToUse.record.data;
        const { resModel, resIds } = values;

        const serviceRecord = await this.orm.webSearchRead(
            service_res_model,
            [["id", "=", service_res_id.resId]],
            {
                specification: {
                    id: {},
                    vehicle_brand: {},
                    vehicle_model: {},
                    vehicle_year: {},
                    vehicle_category_id: {
                        fields: {
                            id: {},
                            display_name: {},
                        },
                    },
                    vehicle_plate: {},
                    vehicle_color: {},
                },
            }
        );

        if (this.isDestroyed || currentRequestId !== this.loadRequestId) return;

        const result = await this.orm.webSearchRead(
            resModel,
            [["id", "in", resIds], ["selected", "=", true], ["state", "in", ["accepted", "assigned", "cancel", "cancel_event", "cancel_supplier"]]],
            {
                specification: {
                    id: {},
                    supplier_id: {
                        fields: {
                            id: {},
                            display_name: {},
                        },
                    },
                    selected: {},
                    state: {},
                    stage_id: {
                        fields: {
                            display_name: {},
                        },
                    },
                    acceptance_date: {},
                },
                order: "acceptance_date asc",
            }
        );

        if (this.isDestroyed || currentRequestId !== this.loadRequestId) return;

        const eventData = await this.orm.webSearchRead(
            "ike.event",
            [["id", "=", propsToUse.record.resId]],
            {
                specification: {
                    location_label: {},
                    destination_label: {},
                    destination_distance: {},
                    event_type_id: {},
                },
            }
        );

        if (this.isDestroyed || currentRequestId !== this.loadRequestId) return;

        const location_label = eventData.records[0].location_label;
        const destination_label = eventData.records[0].destination_label;
        const distance = eventData.records[0].destination_distance;

        this.state.vehicleRecord = serviceRecord.records[0] || {};
        this.state.suppliers = result.records || [];
        this.state.locations = {
            ...eventData.records[0],
            location_label: markup(location_label || ""),
            destination_label: markup(destination_label || ""),
            destination_distance: `${((distance || 0) / 1000).toFixed(3)} km`,
        };
    }

    get context() {
        return this.props.record.context;
    }

    async openSupplierTravelDetails(id, supplier_title, supplier_name) {
        const action = await this.orm.call(
            "ike.event.supplier",
            "action_open_travel_tracking",
            [id],
            {
                context: this.context,
            }
        );
        action.name = supplier_title + supplier_name;
        await this.action.doAction(action);
    }
}

export const ikeSelectedSuppliersInfo = {
    component: IkeSelectedSuppliersInfo,
    additionalClasses: ["ike_selected_suppliers_info"],
};

registry.category("fields").add("ike_selected_suppliers_info", ikeSelectedSuppliersInfo);