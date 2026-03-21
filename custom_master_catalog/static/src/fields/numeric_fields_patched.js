import { IntegerField, integerField } from "@web/views/fields/integer/integer_field";
import { FloatField, floatField } from "@web/views/fields/float/float_field";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";


// INTEGER
patch(IntegerField, {
    props: {
        ...IntegerField.props,
        postfixText: { type: String, optional: true },
    },
});

patch(IntegerField.prototype, {
    setup() {
        super.setup();
        this.postfixText = this.props.postfixText ? " " + _t(this.props.postfixText) : null;
    },
});
IntegerField.template = "custom_master_catalog.IntegerField";

const patchIntegerField = () => ({
    extractProps({ options }) {
        const props = super.extractProps(...arguments);
        props.postfixText = options.postfix;
        return props;
    },
    supportedOptions: [{
        label: "Postfix",
        name: "postfix",
        type: "string",
        default: false,
    }],
});

patch(integerField, patchIntegerField());


// FLOAT
patch(FloatField, {
    props: {
        ...FloatField.props,
        postfixText: { type: String, optional: true },
    },
});

patch(FloatField.prototype, {
    setup() {
        super.setup();
        this.postfixText = this.props.postfixText ? " " + _t(this.props.postfixText) : null;
    },
});
FloatField.template = "custom_master_catalog.FloatField";

const patchFloatField = () => ({
    extractProps({ options }) {
        const props = super.extractProps(...arguments);
        props.postfixText = options.postfix;
        return props;
    },
    supportedOptions: [{
        label: "Postfix",
        name: "postfix",
        type: "string",
        default: false,
    }],
});

patch(floatField, patchFloatField());