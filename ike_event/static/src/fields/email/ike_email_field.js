import { EmailField, emailField } from "@web/views/fields/email/email_field";
import { registry } from "@web/core/registry";
import { useInputField } from "@web/views/fields/input_field_hook";


export class IkeEmailField extends EmailField {
    static template = "ike_event.IkeEmailField";

    setup() {
        useInputField({
            getValue: () => this.props.record.data[this.props.name] || "",
            parse: (v) => this.parse(v),
        });
    }

    parse(value) {
        if (!value) {
            return value;
        }
        const regexEmail = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (regexEmail.test(value)) {
            return value;
        } else {
            throw new Error("Email Invalid");
        }
    }

    get label() {
        return this.props.placeholder || this.props.record.fields[this.props.name].string;
    }
}

export const ikeEmailField = {
    ...emailField,
    component: IkeEmailField,
}

registry.category("fields").add("ike_email", ikeEmailField);
