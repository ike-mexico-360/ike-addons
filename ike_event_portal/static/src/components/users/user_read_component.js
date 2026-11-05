/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { deserializeDate, formatDate } from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { UserPasswordDialog } from "./user_password_dialog";
import { user } from "@web/core/user";

export class UserReadComponent extends Component {
    static template = "ike_event_portal.UserReadComponent";
    static props = {
        userId: { type: Number, optional: true },
        onClose: { type: Function, optional: true },
        onUserUpdated: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.state = useState({
            user: null,
            isLoading: false,
            error: null,
            // Supplier relation of the user (attention center, supplier, user type)
            rel: null,
            // Edit mode
            isEditing: false,
            isSaving: false,
            form: {},
            formErrors: {},
            saveError: null,
            // Select options (loaded only when editing)
            countries: [],
            states: [],
            supplierCenters: [],
        });

        onWillStart(async () => {
            if (this.props.userId) {
                await this.loadUser(this.props.userId);
            }
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps.userId && nextProps.userId !== this.props.userId) {
                await this.loadUser(nextProps.userId);
            }
        });
    }

    get isOperator() {
        return Boolean(this.state.rel && this.state.rel.user_type === "operator");
    }

    // Load
    async loadUser(id) {
        this.state.isLoading = true;
        this.state.isEditing = false;
        this.state.error = null;
        try {
            const [userData] = await rpc('/provider/portal/users/search', {
                domain: [['id', '=', id]],
                fields: [
                    'name', 'login', 'email', 'phone',
                    'street', 'street2', 'zip', 'city', 'country_id', 'state_id',
                    'partner_id', 'groups_id', 'active'
                ]
            });

            this.state.user = userData;
            this.state.user.center_of_attention_name = await this.getCenterAttentionName(id);

            // Partner data: license number (vat), dates and colony
            if (userData && userData.partner_id) {
                const [partnerData] = await this.orm.read(
                    'res.partner', [userData.partner_id[0]],
                    ['vat', 'x_birthdate', 'x_license_expiration_date', 'l10n_mx_edi_colony']
                );
                this.state.partner_vat = partnerData.vat;
                this.state.partner_colony = partnerData.l10n_mx_edi_colony;
                // Raw values ("YYYY-MM-DD") for the date inputs
                this.state.partner_birthdate_raw = partnerData.x_birthdate;
                this.state.partner_license_expiration_raw = partnerData.x_license_expiration_date;
                // Formatted values for the read view
                this.state.partner_birthdate = this.formatPartnerDate(partnerData.x_birthdate);
                this.state.partner_license_expiration = this.formatPartnerDate(partnerData.x_license_expiration_date);
            }
        } catch (error) {
            console.error("Error loading user:", error);
            this.state.error = _t("Failed to load user details.");
        } finally {
            this.state.isLoading = false;
        }
    }

    // "2027-01-31" -> date in the user's language format (e.g. 31/01/2027)
    formatPartnerDate(value) {
        return value ? formatDate(deserializeDate(value)) : false;
    }

    async getCenterAttentionName(user_id) {
        try {
            const supplier_driver = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [['user_id', 'in', [user_id]]],
                ['center_of_attention_id', 'supplier_id', 'user_type']
            );
            if (supplier_driver.length > 0) {
                // Keep the relation: used by edit mode
                this.state.rel = supplier_driver[0];
                return supplier_driver[0].center_of_attention_id[1];
            }
            this.state.rel = null;
        } catch (error) {
            console.error("Error fetching center of attention name:", error);
            return _t("Unknown Center");
        }
    }

    // ### Edit mode ###
    async startEdit() {
        const u = this.state.user;
        // 1. Copy the current data into the form (the read view is not touched)
        this.state.form = {
            name: u.name || "",
            phone: u.phone || "",
            active: u.active || false,
            birthdate: this.state.partner_birthdate_raw || "",
            vat: this.state.partner_vat || "",
            license_validity: this.state.partner_license_expiration_raw || "",
            street: u.street || "",
            street2: u.street2 || "",
            colony: this.state.partner_colony || "",
            zip: u.zip || "",
            city: u.city || "",
            country_id: u.country_id ? u.country_id[0] : "",
            state_id: u.state_id ? u.state_id[0] : "",
            center_of_attention_id: this.state.rel ? this.state.rel.center_of_attention_id[0] : "",
        };
        // 2. Clear previous errors
        this.state.formErrors = {};
        this.state.saveError = null;
        // 3. Load select options (countries, states, attention centers)
        await this.loadEditOptions();
        // 4. Switch to edit mode: OWL re-renders the inputs
        this.state.isEditing = true;
    }

    cancelEdit() {
        // The typed values only live in state.form, so they are simply discarded
        this.state.isEditing = false;
        this.state.formErrors = {};
        this.state.saveError = null;
    }

    async loadEditOptions() {
        // Countries and centers are loaded only the first time
        if (!this.state.countries.length) {
            this.state.countries = await this.orm.searchRead(
                'res.country', [], ['id', 'name'], { order: 'name asc' }
            );
        }
        if (this.state.rel && !this.state.supplierCenters.length) {
            this.state.supplierCenters = await rpc('/api/partners/centers', {
                partner_id: this.state.rel.supplier_id[0],
            });
        }
        await this.loadStates(this.state.form.country_id);
    }

    async loadStates(countryId) {
        this.state.states = countryId
            ? await this.orm.searchRead(
                'res.country.state', [['country_id', '=', countryId]], ['id', 'name'], { order: 'name asc' }
            )
            : [];
    }

    async onCountryChange(ev) {
        const countryId = parseInt(ev.target.value) || "";
        this.state.form.country_id = countryId;
        this.state.form.state_id = "";
        await this.loadStates(countryId);
    }

    validateEdit() {
        const form = this.state.form;
        const errors = {};

        // Required for every user type
        const required = {
            name: _t("Name is required"),
            center_of_attention_id: _t("Attention center is required"),
        };
        // Operators keep the same required fields as on creation
        if (this.isOperator) {
            Object.assign(required, {
                phone: _t("Phone is required"),
                vat: _t("License number is required"),
                license_validity: _t("License expiration date is required"),
            });
        }

        for (const [field, message] of Object.entries(required)) {
            if (!String(form[field] || "").trim()) {
                errors[field] = message;
            }
        }

        this.state.formErrors = errors;
        return Object.keys(errors).length === 0;
    }

    async saveEdit() {
        if (!this.validateEdit()) {
            return;
        }
        this.state.isSaving = true;
        this.state.saveError = null;
        try {
            const result = await rpc('/provider/portal/user/update/json', {
                user_id: this.state.user.id,
                ...this.state.form,
            });
            if (!result || !result.success) {
                this.state.saveError = (result && result.error) || _t("The user could not be updated.");
                return;
            }

            // Reload the read view with the saved data
            await this.loadUser(this.state.user.id);
            this.dialog.add(AlertDialog, {
                title: _t("User updated"),
                body: _t("The changes were saved successfully."),
            });
            // Let the parent refresh its list (e.g. the name changed)
            if (this.props.onUserUpdated) {
                this.props.onUserUpdated();
            }
        } catch (error) {
            console.error("Error updating user:", error);
            this.state.saveError = _t("The user could not be updated.");
        } finally {
            this.state.isSaving = false;
        }
    }

    openPasswordDialog() {
        this.dialog.add(UserPasswordDialog, {
            userId: this.state.user.id,
            userName: this.state.user.name,
            onPasswordChanged: () => {
                this.dialog.add(AlertDialog, {
                    title: _t("Password changed"),
                    body: _t("The password was changed successfully."),
                });
            },
        });
    }

    get isCurrentUser() {
        return Boolean(this.state.user && this.state.user.id === user.userId);
    }

}

registry.category("public_components").add("ike_event_portal.UserReadComponent", UserReadComponent);
