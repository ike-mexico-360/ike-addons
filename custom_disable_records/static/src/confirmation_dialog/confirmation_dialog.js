import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

import { useState } from "@odoo/owl";

export class CustomConfirmationDialog extends ConfirmationDialog {
    static template = "custom_disable_records.CustomConfirmationDialog";
    setup() {
        super.setup();
        this.state = useState({
            'reason': '',
        });
    }
    async execButton(callback) {
        if (this.isProcess) {
            return;
        }
        this.setButtonsDisabled(true);
        if (callback) {
            let shouldClose;
            try {
                shouldClose = await callback(this.state.reason);
            } catch (e) {
                this.props.close();
                throw e;
            }
            if (shouldClose === false) {
                this.setButtonsDisabled(false);
                return;
            }
        }
        this.props.close();
    }
}
