import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { useInputField } from "@web/views/fields/input_field_hook";

import { useEffect, useExternalListener, useRef } from "@odoo/owl";

export class IkeCharField extends CharField {
    setup() {
        // console.log("IkeCharField", this);
        this.input = useRef("input");
        if (this.props.dynamicPlaceholder) {
            this.dynamicPlaceholder = useDynamicPlaceholder(this.input);
            useExternalListener(document, "keydown", this.dynamicPlaceholder.onKeydown);
            useEffect(() =>
                this.dynamicPlaceholder.updateModel(
                    this.props.dynamicPlaceholderModelReferenceField
                )
            );
        }
        this.inputRef = useInputField({
            getValue: () => this.formattedValue,
            parse: (v) => this.parse(v),
        });

        this.selectionStart = this.props.record.data[this.props.name]?.length || 0;
    }
    parse(value) {
        value = super.parse(value);
        const regexString = this.props.regex;

        if (value && regexString) {
            const regex = new RegExp(regexString);
            if (regex.test(value)) {
                return value;
            } else {
                throw new Error("Invalid Input");
            }
        }
        return value;
    }
    applyMask(value, mask, filler = "*") {
        const strValue = String(value);
        let result = "";
        let index = 0;

        if (mask.length < value.length) {
            mask += "#".repeat(value.length - mask.length);
        }

        for (let char of mask) {
            if (char === "#") {
                result += strValue[index] ?? filler;
            } else {
                result += char;
            }
            index++;
        }

        return result;
    }
    get formattedValue() {
        let value = this.props.record.data[this.props.name] || "";
        if (this.mask) {
            return this.applyMask(value, this.mask);
        }
        return value;
    }
    get mask() {
        if (!this.props.mask) {
            return null;
        }
        return this.props.mask.includes('#') ? this.props.mask : this.props.record.data[this.props.mask];
    }
    get label() {
        return this.props.placeholder || this.props.record.fields[this.props.name].string;
    }
    get isTranslatable() {
        return !this.props.noTranslate && this.props.record.fields[this.props.name].translate;
    }
    onFocus() {
        this.inputRef.el.value = this.props.record.data[this.props.name] || "";
    }
    onBlur() {
        this.selectionStart = this.input.el.selectionStart;
        this.inputRef.el.value = this.formattedValue;
    }
}
IkeCharField.template = "ike_event.IkeCharField";
IkeCharField.props = {
    ...CharField.props,
    noTranslate: { type: Boolean, optional: true },
    regex: { type: [Function, String], optional: true },
    mask: { type: [Function, String], optional: true },
};

export const ikeCharField = {
    ...charField,
    component: IkeCharField,
    extractProps({ options }) {
        const props = charField.extractProps(...arguments);
        props.noTranslate = options.no_translate;
        props.regex = options.regex;
        props.mask = options.mask;
        return props;
    },
    supportedOptions: [{
        label: "No Translate",
        name: "no_translate",
        type: "boolean",
        default: false,
    }, {
        label: "Regex",
        name: "regex",
        type: "string",
    }, {
        label: "Mask",
        name: "mask",
        type: "string",
    }],
};

registry.category("fields").add("ike_char", ikeCharField);
