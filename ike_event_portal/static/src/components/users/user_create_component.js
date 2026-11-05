/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { user } from "@web/core/user";
import { unaccent } from "@web/core/utils/strings";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { _t } from "@web/core/l10n/translation";

export class UserCreateComponent extends Component {
    static template = "ike_event_portal.UserCreateComponent";
    static props = {
        onUserCreated: { type: Function },
        onCancel: { type: Function },
    };

    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.user = user;
        this.state = useState({
            formData: {
                firstname: "",
                lastname: "",
                birthdate: "",
                email: "",
                password: "",
                phone: "",
                license_type: "",
                license_number: "",
                license_validity: "",
                user_type: "operator", // Default
                street: "",
                street2: "",
                colony: "",
                zip: "",
                municipality: "",
                state_id: "",
                country_id: "",
                center_of_attention_id: ""
            },
            countries: [],
            states: [],
            isSubmitting: false,
            error: null,
            errors: {
                firstname: ""
            },
        });

        onWillStart(async () => {
            // 1. Fetch Countries
            const countriesPromise = this.orm.searchRead(
                'res.country', [], ['id', 'name', 'code'], { order: 'name asc' }
            );

            const [countries] = await Promise.all([countriesPromise]);

            this.state.countries = countries;
            const mexico = this.state.countries.find(c => c.code === 'MX');
            if (mexico) {
                this.state.formData.country_id = mexico.id;
                const states = await this.orm.searchRead(
                    'res.country.state',
                    [['country_id', '=', mexico.id]],
                    ['id', 'name'],
                    { order: 'name asc' }
                );
                this.state.states = states;
            }
            await this.getSupplierId();
            await this.loadSupplierCenters();
        });
    }

    get isOperator() {
        return this.state.formData.user_type === "operator";
    }

    get operatorLogin() {
        const clean = (text) => unaccent((text || "").trim()).replace(/[^a-z0-9]/g, "");
        const firstLastname = this.state.formData.lastname.trim().split(/\s+/)[0] || "";
        return clean(this.state.formData.firstname).slice(0, 2) + clean(firstLastname);
    }

    onUserTypeChange() {
        this.state.errors = {};
        this.state.error = null;
    }

    async onCountryChange(ev) {
        const val = ev.target.value;
        const countryId = val ? parseInt(val) : false;
        this.state.formData.country_id = countryId;
        this.state.formData.state_id = "";
        this.state.states = [];

        if (countryId) {
            try {
                const states = await this.orm.searchRead(
                    'res.country.state',
                    [['country_id', '=', countryId]],
                    ['id', 'name'],
                    { order: 'name asc' }
                );
                this.state.states = states;
            } catch (error) {
                console.error("Error fetching states", error);
            }
        }
    }

    async saveUser() {
        this.state.error = null;
        this.state.isSubmitting = true;
        const data = this.state.formData;
        if (!this.validateForm()) {
            // Stop submission if invalid
            console.log("Validation failed");
            this.state.isSubmitting = false;
            return;
        }

        if(this.supplier_id === 0){
            this.state.error = "Could not determine the supplier. Please contact the administrator.";
            this.state.isSubmitting = false;
            return;
        }

        try {
            // 2. Resolve Groups

            // Map the radio selection to the XML name suffix
            const roleXmlMap = {
                'financial': 'financial',
                'supervisor': 'supervisor',
                'operator': 'operator',
            };
            const roleXmlName = roleXmlMap[data.user_type];

            // 3. Prepare User Payload
            const fullName = `${data.firstname} ${data.lastname || ''}`.trim();

            const userPayload = {
                name: fullName,
                // Operador: login generado y sin email. Otros tipos: el email es el login
                login: this.isOperator ? this.operatorLogin : data.email,
                email: this.isOperator ? "" : data.email,
                password: data.password || 'P@ssw0rd123',

                // Address fields (Standard Odoo fields on res.users/res.partner)

                user_type: roleXmlName,
                phone: data.phone,
                street: data.street,
                street2: data.street2,
                zip: data.zip,
                city: data.municipality,
                country_id: data.country_id ? parseInt(data.country_id) : false,
                state_id: data.state_id ? parseInt(data.state_id) : false,
                supplier_id: this.supplier_id,
                center_of_attention_id: data.center_of_attention_id ? parseInt(data.center_of_attention_id) : false,
                birthdate: data.birthdate,
                licence_type: data.license_type,
                license_validity: data.license_validity,
                vat: data.license_number, // Mapping license number to VAT as per your python code
                user: this.user.userId,
            };

            console.log("Creating user with payload:", userPayload);

            // 4. Create User
            const result = await rpc('/provider/portal/user/create/json', userPayload);
            console.log("result:", result);

                        if (!result || !result.success) {
                this.state.error = (result && result.error) || "The user could not be created.";
                return;
            }

            // Mostrar el login con el que quedó el usuario (Operador puede traer consecutivo)
            this.dialog.add(AlertDialog, {
                title: _t("User created"),
                body: _t("The user was created with the login: %s", result.login),
            });

            this.props.onUserCreated();

        } catch (err) {
            console.error("Error creating user:", err);
            this.state.error = err.message || "Error creating user. Email might be duplicated.";
        } finally {
            this.state.isSubmitting = false;
        }
    }

    validateForm() {
        const data = this.state.formData;
        const errors = {};

        // Obligatorio para todos
        const required = {
            firstname: _t("The name is required"),
            password: _t("The password is required"),
            center_of_attention_id: _t("The attention center is requierd"),
        };
        // Política de contraseña
        const passwordPolicy = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{8,}$/;
        if (data.password && !errors.password && !passwordPolicy.test(data.password)) {
            errors.password = _t("The password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one number.");
        }

        if (this.isOperator) {
            // Operador: el login se genera, el email no se pide
            Object.assign(required, {
                lastname: _t("The lastname is required"),
                phone: _t("The phone is required"),
                license_type: _t("Type of license is required"),
                license_number: _t("The license number is required"),
                license_validity: _t("The license validity date is required"),
            });
        } else {
            // Financieros / Supervisor: el email es el login
            required.email = _t("The email is required");
        }

        for (const [field, message] of Object.entries(required)) {
            if (!String(data[field] || "").trim()) {
                errors[field] = message;
            }
        }

        this.state.errors = errors; // Update state to show errors in UI
        return Object.keys(errors).length === 0;
    }

    async getSupplierId() {
        try {
            let supplier_drivers = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [],
                []
            );
            let supplier = supplier_drivers.find(x => x.user_id[0] === this.user.userId);
            this.supplier_id = supplier.supplier_id[0];
        }
        catch (e) {

        }

    }

    async loadSupplierCenters() {
        console.log('Loading supplier centers for partner ID:', this.supplier_id);
        try {
            const result = await rpc('/api/partners/centers', {
                partner_id: this.supplier_id
            });

            console.log('Supplier Centers:', result);
            this.state.supplierCenters = result; // Store in state if needed
            return result;
        } catch (error) {
            console.error('Error loading supplier centers:', error);
            this.state.error = 'Error loading supplier centers';
        }
    }
}

registry.category("public_components").add("ike_event_portal.UserCreateComponent", UserCreateComponent);