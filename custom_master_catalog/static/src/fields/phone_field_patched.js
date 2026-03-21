import { patch } from "@web/core/utils/patch";
import { useInputField } from "@web/views/fields/input_field_hook";
import { PhoneField, phoneField, formPhoneField } from "@web/views/fields/phone/phone_field";

import { Component, useState } from "@odoo/owl";

patch(PhoneField, {
    defaultProps: {
        ...PhoneField.defaultProps,
        enableCall: true,
        humanReadable: true,
    },
    props: {
        ...PhoneField.props,
        enableCall: { type: Boolean, optional: true },
        humanReadable: { type: Boolean, optional: true },
    },
});

// patch(PhoneField.prototype, {
//     /** @override **/
//     setup() {
//         // console.log("PhoneField", this);
//         this.inputRef = useInputField({
//             getValue: () => this.formattedValue,
//             refName: "input",
//             parse: (v) => this.parse(v),
//         });
//     },
//     parse(value) {
//         if (!value) {
//             return value;
//         }
//         value = value.replace(/[+\s()]/g, ''); // Remove All formatted symbols
//         const regexEmail = /^\d{10,12}$/;
//         if (regexEmail.test(value)) {
//             return value;
//         } else {
//             throw new Error("Phone Invalid");
//         }
//     },
//     get formattedValue() {
//         const value = this.props.record.data[this.props.name] || "";
//         if (!this.props.humanReadable) {
//             return value;
//         }
//         // Mexico
//         let digits = value.replace(/\D/g, "").replace(" ", "");
//         if (digits.length == 10) {
//             return digits.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2 $3');
//         } else if (digits.length == 12 && digits.startsWith('52')) {
//             return digits.replace(/52(\d{2})(\d{4})(\d{4})/, '+52 ($1) $2 $3');
//         } else {
//             return value;
//         }
//     },
// });

const patchPhoneField = () => ({
    extractProps({ options }) {
        const props = super.extractProps(...arguments);
        props.enableCall = options.enable_call;
        return props;
    },
    supportedOptions: [{
        label: "Enable Call",
        name: "enable_call",
        type: "boolean",
        default: false,
    }, {
        label: "Human readable",
        name: "human_readable",
        type: "boolean",
        default: true,
    }],
});

patch(phoneField, patchPhoneField());
patch(formPhoneField, patchPhoneField());
