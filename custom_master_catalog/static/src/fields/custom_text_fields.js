import { CharField, charField } from "@web/views/fields/char/char_field";
import { TextField, textField } from "@web/views/fields/text/text_field";
import { HtmlField, htmlField } from "@html_editor/fields/html_field";

import { patch } from "@web/core/utils/patch";

patch(CharField, {
    defaultProps: {
        ...CharField.defaultProps,
        noTranslate: false,
    },
    props: {
        ...CharField.props,
        noTranslate: { type: Boolean, optional: true },
    },
});

patch(CharField.prototype, {
    get isTranslatable() {
        return !this.props.noTranslate && this.props.record.fields[this.props.name].translate;
    }
});

const patchCharField = () => ({
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

patch(charField, patchCharField());

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
