import { registry } from "@web/core/registry";
import { useBus } from "@web/core/utils/hooks";
import { FormController } from '@web/views/form/form_controller';
import { formView } from "@web/views/form/form_view";

import { useSubEnv } from "@odoo/owl";


export class IkeServiceInputScreenFormController extends FormController {
    setup() {
        // console.log("IkeServiceInputScreenFormController", this, this.env.config);
        useSubEnv({
            ...this.env,
            config: {
                ...this.env.config,
                setDisplayName: (newDisplayName) => { },
            },
        });
        super.setup();

        useBus(this.env.bus, "IKE_EVENT:IA_SUGGESTIONS_FINISHED", (event) => {
            this.model.root.update({
                'ia_suggestion_loading': false,
            });
        });
    }
};

IkeServiceInputScreenFormController.components = {
    ...FormController.components,
};

export const ikeServiceInputScreenFormView = {
    ...formView,
    Controller: IkeServiceInputScreenFormController,
}

registry.category("views").add("ike_service_input_screen_form", ikeServiceInputScreenFormView);
