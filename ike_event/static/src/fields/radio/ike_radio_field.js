import { registry } from "@web/core/registry";
import { RadioField, radioField } from "@web/views/fields/radio/radio_field";

export class IkeRadioField extends RadioField {
    static template = "ike_event.IkeRadioField";

    static props = {
        ...RadioField.props,
        icons: { type: Array, optional: true },
    };

    get label() {
        return this.props.record.fields[this.props.name].string;
    }
}

export const ikeRadioField = {
    ...radioField,
    component: IkeRadioField,
    extractProps: ({ options, string }, dynamicInfo) => {
        const props = radioField.extractProps({ options, string }, dynamicInfo);
        props.icons = options.icons || [];
        return props;
    },
    additionalClasses: ["o_ike_radio_field"],
};

registry.category("fields").add("ike_radio", ikeRadioField);
