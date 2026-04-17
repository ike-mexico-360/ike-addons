import { _t } from "@web/core/l10n/translation";
import { onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { FormController } from '@web/views/form/form_controller';
import { formView } from "@web/views/form/form_view";


export class IkeEventServiceAssistviewController extends FormController {
    setup() {
        super.setup();
        this.busService = this.env.services.bus_service;

        onWillStart(async () => {
            this.subscribeToChannel();
        });

        onWillUnmount(() => {
            this.unsubscribeFromChannel();
        });
    }

    subscribeToChannel() {
        const eventId = this.props.context?.default_event_id;
        this.busChannel = `ike_channel_assistview_event_${eventId}`;
        this.busService.addChannel(this.busChannel);
        this.busService.subscribe("ike_event_assistview_reload", this.handleNotification);
        console.log("Subscribed to channel", this.busChannel);
    }

    unsubscribeFromChannel() {
        if (this.busChannel) {
            this.busService.deleteChannel(this.busChannel);
            this.busService.unsubscribe("ike_event_assistview_reload", this.handleNotification);
        }
    }

    handleNotification = async (message) => {
        console.log("Notification", message);
        if (this.model.root.resId) {
            const vals = { received_assistview: true };

            if (message?.brand) vals.brand = message.brand;
            if (message?.model) vals.model = message.model;
            if (message?.plate) vals.plate = message.plate;
            if (message?.color) vals.color = message.color;
            if (message?.year) vals.year = message.year;
            if (message?.location) {
                if (message.location.address) vals.address = message.location.address;
                if (message.location.latitude) vals.latitude = String(message.location.latitude);
                if (message.location.longitude) vals.longitude = String(message.location.longitude);
            }
            if (message?.answers) vals.answers = JSON.parse(JSON.stringify(message.answers));
            if (message?.plate_image) vals.plate_image = message.plate_image;

            // Solo agregar vehicle_images si hay imágenes
            if (message?.vehicle_images && Object.keys(message.vehicle_images).length) {
                vals.vehicle_images = Object.entries(message.vehicle_images).map(([name, encoded]) => [
                    0, 0, { image_name: name, image: encoded }
                ]);
            }

            await this.env.services.orm.write('ike.event.service.assistview', [this.model.root.resId], vals);
            await this.model.root.load();
            console.log("Campo received_assistview marcado en DB");
        }
    }
}

export const ikeEventServiceAssistviewFormView = {
    ...formView,
    Controller: IkeEventServiceAssistviewController,
}

registry.category("views").add("ike_event_service_assistview_form", ikeEventServiceAssistviewFormView);
