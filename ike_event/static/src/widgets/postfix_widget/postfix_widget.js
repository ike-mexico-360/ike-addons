/** @odoo-module **/
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useInputField } from "@web/views/fields/input_field_hook";
import { useNumpadDecimal } from "@web/views/fields/numpad_decimal_hook";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

export class PostfixField extends Component {
    static template = "ike_event.postfixField";
    static props = {
        ...standardFieldProps,
        placeholder: { type: String, optional: true },
        postfix: { type: String, optional: true },
    };

    setup() {
        useInputField({
            getValue: () => this.props.record.data[this.props.name] || "",
            refName: "numpadDecimal",
            parse: (v) => {
                if (v === null || v === undefined || v === '') return 0;

                const number = Number(v);
                if (isNaN(number)) return 0;

                return Number.isInteger(number) ? Math.trunc(number) : number;
            },
        });
        useNumpadDecimal();
    }

    get postfixText() {
        return this.props.postfix ? _t(this.props.postfix) : _t("");
    }

    get formattedValue() {
        const val = this.props.record.data[this.props.name];
        return `${val || 0} ${this.postfixText}`;
    }
}

export const postfixField = {
    component: PostfixField,
    displayName: _t("Postfix Field"),
    supportedTypes: ["integer", "float"],
    extractProps: ({ attrs, options }) => ({
        placeholder: attrs.placeholder,
        postfix: attrs.postfix || options.postfix,
    }),
};

registry.category("fields").add("postfix_field", postfixField);

