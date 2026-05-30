/** @odoo-module **/

import { registry } from "@web/core/registry";
import { PhoneField, phoneField } from "@web/views/fields/phone/phone_field";
import { useInputField } from "@web/views/fields/input_field_hook";

export class CustomPhoneField extends PhoneField {
    static template = "custom_nu.custom_phone";

    setup() {
        useInputField({
            getValue: () => this.formattedValue,
            parse: (v) => {
                if (!v) return v;
                const cleaned = v.replace(/\D/g, "");
                const regexPhone = /^\d{10,12}$/;
                if (!regexPhone.test(cleaned)) {
                    throw new Error("Phone Invalid");
                }
                return cleaned;
            },
        });
    }

    get rawValue() {
        return this.props.record.data[this.props.name] || "";
    }

    get formattedValue() {
        const digits = (this.rawValue || "").replace(/\D/g, "");
        if (digits.length === 10) {
            return digits.replace(/(\d{2})(\d{4})(\d{4})/, "$1 $2 $3");
        }
        return digits;
    }
}

registry.category("fields").add("ike_custom_phone", {
    ...phoneField,                  // hereda extractProps, supportedTypes, etc.
    component: CustomPhoneField,
});