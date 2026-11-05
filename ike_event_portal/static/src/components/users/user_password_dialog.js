/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

// At least 8 characters, one uppercase letter, one lowercase letter and one number
const PASSWORD_POLICY = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;

export class UserPasswordDialog extends Component {
    static template = "ike_event_portal.UserPasswordDialog";
    static components = { Dialog };
    static props = {
        close: Function, // injected by the dialog service
        userId: Number,
        userName: { type: String, optional: true },
        onPasswordChanged: { type: Function, optional: true },
    };

    setup() {
        this.state = useState({
            password: "",
            confirmPassword: "",
            errors: {},
            saveError: null,
            isSaving: false,
        });
    }

    validate() {
        const { password, confirmPassword } = this.state;
        const errors = {};

        if (!password) {
            errors.password = _t("Password is required");
        } else if (!PASSWORD_POLICY.test(password)) {
            errors.password = _t(
                "The password must have at least 8 characters, one uppercase letter, one lowercase letter and one number."
            );
        }
        if (!confirmPassword) {
            errors.confirmPassword = _t("Please confirm the password");
        } else if (password && confirmPassword !== password) {
            errors.confirmPassword = _t("Passwords do not match");
        }

        this.state.errors = errors;
        return Object.keys(errors).length === 0;
    }

    async save() {
        if (!this.validate()) {
            return;
        }
        this.state.isSaving = true;
        this.state.saveError = null;
        try {
            const result = await rpc("/provider/portal/user/password/json", {
                user_id: this.props.userId,
                password: this.state.password,
            });
            if (!result || !result.success) {
                this.state.saveError = (result && result.error) || _t("The password could not be changed.");
                return;
            }
            if (this.props.onPasswordChanged) {
                this.props.onPasswordChanged();
            }
            this.props.close();
        } catch (error) {
            console.error("Error changing password:", error);
            this.state.saveError = _t("The password could not be changed.");
        } finally {
            this.state.isSaving = false;
        }
    }
}
