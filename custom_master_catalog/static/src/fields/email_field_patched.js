import { patch } from "@web/core/utils/patch";
import { useInputField } from "@web/views/fields/input_field_hook";
import { EmailField } from "@web/views/fields/email/email_field";

patch(EmailField.prototype, {
    /** @override **/
    setup() {
        useInputField({
            getValue: () => this.props.record.data[this.props.name] || "",
            refName: "input",
            parse: (v) => this.parse(v),
        });
    },
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
});