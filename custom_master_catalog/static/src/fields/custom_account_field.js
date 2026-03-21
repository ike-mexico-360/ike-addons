import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useInputField } from "@web/views/fields/input_field_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";

import { Component, useState } from "@odoo/owl";


export class CustomNumericAccountField extends Component {
    static template = "custom_master_catalog.CustomNumericAccountField";
    static props = {
        ...standardFieldProps,
        inputType: { type: String, optional: true },
        placeholder: { type: String, optional: true },
    };
    static defaultProps = {
        inputType: "text",
    };
    setup() {
        console.log("CustomAccountField", this);
        this.state = useState({
            hasFocus: false,
        });
        useInputField({
            getValue: () => this.formattedValue,
            refName: "numpadDecimal",
            parse: (v) => this.parseAccount(v),
        });
        useNumpadDecimal();
    }

    onFocusIn() {
        this.state.hasFocus = true;
    }

    onFocusOut() {
        this.state.hasFocus = false;
    }
    parseAccount(value) {
        return value.replace(/\D+/g, '');
    }

    get formattedValue() {
        return this.value;
    }

    get value() {
        return this.props.record.data[this.props.name];
    }
}

export const customNumericAccountField = {
    component: CustomNumericAccountField,
    displayName: "Custom Numeric Account Field",
    supportedTypes: ["char"],
    isEmpty: (record, fieldName) => record.data[fieldName] === false,
    extractProps: ({ attrs, options }) => ({
        inputType: options.type,
        placeholder: attrs.placeholder,
    }),
};

registry.category("fields").add("custom_numeric_account", customNumericAccountField);
