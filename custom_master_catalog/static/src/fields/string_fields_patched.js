import { CharField, charField } from "@web/views/fields/char/char_field";
import { TextField, textField } from "@web/views/fields/text/text_field";
import { HtmlField, htmlField } from "@html_editor/fields/html_field";
import { useInputField } from "@web/views/fields/input_field_hook";

import { patch } from "@web/core/utils/patch";


// Char
patch(CharField, {
    props: {
        ...CharField.props,
        noTranslate: { type: Boolean, optional: true },
        regex: { type: String, optional: true },
    },
    defaultProps: {
        ...CharField.defaultProps,
        noTranslate: false,
    },
});

patch(CharField.prototype, {
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
    },
    get isTranslatable() {
        return !this.props.noTranslate && this.props.record.fields[this.props.name].translate;
    },
});

const patchCharField = () => ({
    extractProps({ options }) {
        const props = super.extractProps(...arguments);
        props.noTranslate = options.no_translate;
        props.regex = options.regex;
        return props;
    },
    supportedOptions: [{
        label: "No Translate",
        name: "no_translate",
        type: "boolean",
        default: false,
    }, {
        label: "regex",
        name: "regex",
        type: "string",
    }],
});

patch(charField, patchCharField());


// Text
patch(TextField, {
    defaultProps: {
        ...TextField.defaultProps,
        noTranslate: false,
    },
    props: {
        ...TextField.props,
        noTranslate: { type: Boolean, optional: true },
    },
});

patch(TextField.prototype, {
    get isTranslatable() {
        return !this.props.noTranslate && this.props.record.fields[this.props.name].translate;
    }
});

const patchTextField = () => ({
    extractProps({ options }) {
        const props = super.extractProps(...arguments);
        props.noTranslate = options.no_translate;
        return props;
    },
    supportedOptions: [{
        label: "No Translate",
        name: "no_translate",
        type: "boolean",
        default: false,
    }],
});

patch(textField, patchTextField());


// Html
patch(HtmlField, {
    defaultProps: {
        ...HtmlField.defaultProps,
        noTranslate: false,
    },
    props: {
        ...HtmlField.props,
        noTranslate: { type: Boolean, optional: true },
    },
});

patch(HtmlField.prototype, {
    get isTranslatable() {
        return !this.props.noTranslate && this.props.record.fields[this.props.name].translate;
    }
});

const patchHtmlField = () => ({
    extractProps({ options }) {
        const props = super.extractProps(...arguments);
        props.noTranslate = options.no_translate;
        return props;
    },
    supportedOptions: [{
        label: "No Translate",
        name: "no_translate",
        type: "boolean",
        default: false,
    }],
});

patch(htmlField, patchHtmlField());
