/** @odoo-module **/
import { IkeServiceInputScreenFormController } from "@ike_event/views/ike_service_input_screen_form";
import { patch } from "@web/core/utils/patch";
import { useBus } from "@web/core/utils/hooks";


patch(IkeServiceInputScreenFormController.prototype, {
    setup() {
        super.setup();

        // Recargar datos de la vista
        useBus(this.env.bus, "IKE_SERVICE_INPUT:SET_OPENAI_SUGGESTED_VALUES", async (ev) => {
            const recordId = ev.detail.recordId;

            if (!recordId) return;

            // Comparar el registro actual de la vista contra el recordId que se escribió
            if (this.model.root.resId === ev.detail.recordId) {
                await this.model.root.load();
            }
        });
    },
});
