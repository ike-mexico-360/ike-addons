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
        this.busService.subscribe("ike_event_assistview_reload", this.handleNotification );
        console.log("Subscribed to channel", this.busChannel);
    }

    unsubscribeFromChannel() {
        if (this.busChannel) {
            this.busService.deleteChannel(this.busChannel);
            this.busService.unsubscribe("ike_event_assistview_reload", this.handleNotification );
        }
    }

    handleNotification  = async (message) => {
        console.log("Notification", message);
        if (message?.brand) {
            await this.model.root.update({ brand: message.brand });
            console.log("Campo brand actualizado:", message.brand);
        }
        if (message?.model) {
            await this.model.root.update({ model: message.model });
            console.log("Campo model actualizado:", message.model);
        }
        if (message?.plate) {
            await this.model.root.update({ plate: message.plate });
            console.log("Campo plate actualizado:", message.plate);
        }
        if (message?.color) {
            await this.model.root.update({ color: message.color });
            console.log("Campo color actualizado:", message.color);
        }
        if (message?.location) {
            await this.model.root.update({
                address: message.location.address,
                latitude: message.location.latitude,
                longitude: message.location.longitude,
            })
            console.log("Actualizando ubicación");
        }
        if (message?.answers) {
            const cleanAnswers = JSON.parse(JSON.stringify(message.answers));
            await this.model.root.update({ answers: cleanAnswers });
            console.log("Actualizando respuestas", cleanAnswers);
        }
    }
}

export const ikeEventServiceAssistviewFormView = {
    ...formView,
    Controller: IkeEventServiceAssistviewController,
}

registry.category("views").add("ike_event_service_assistview_form", ikeEventServiceAssistviewFormView);
