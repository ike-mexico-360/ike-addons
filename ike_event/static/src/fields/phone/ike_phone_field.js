import { PhoneField, phoneField } from "@web/views/fields/phone/phone_field";
import { useInputField } from "@web/views/fields/input_field_hook";

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

export class IkePhoneField extends PhoneField {
    static template = "ike_event.IkePhoneField";

    static props = {
        ...PhoneField.props,
        humanReadable: { type: Boolean, optional: true },
    };

    static defaultProps = {
        ...PhoneField.defaultProps,
        humanReadable: true,
    };

    setup() {
        this.inputRef = useInputField({
            getValue: () => this.formattedValue,
            parse: (v) => this.parse(v),
        });
    }

    parse(value) {
        if (!value) {
            return value;
        }
        value = value.replace(/[+\s()]/g, ''); // Remove All formatted symbols
        const regexPhone = /^\d{10,12}$/;
        if (regexPhone.test(value)) {
            return value;
        } else {
            throw new Error("Phone Invalid");
        }
    }

    get formattedValue() {
        const value = this.props.record.data[this.props.name] || "";
        if (!this.props.humanReadable) {
            return value;
        }
        // Mexico
        let digits = value.replace(/\D/g, "").replace(" ", "");
        if (digits.length == 10) {
            return digits.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2 $3');
        } else if (digits.length == 12 && digits.startsWith('52')) {
            return digits.replace(/52(\d{2})(\d{4})(\d{4})/, '+52 ($1) $2 $3');
        } else {
            return value;
        }
    }

    get label() {
        return this.props.placeholder || this.props.record.fields[this.props.name].string;
    }
}

export const ikePhoneField = {
    ...phoneField,
    component: IkePhoneField,
};

registry.category("fields").add("ike_phone", ikePhoneField);
