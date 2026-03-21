/** @odoo-module **/

import { registry } from "@web/core/registry";
import { BooleanField } from "@web/views/fields/boolean/boolean_field";

export class IkeCheckboxField extends BooleanField {
    static template = "ike_event.IkeCheckboxField";

    get label() {
        return this.props.record.fields[this.props.name].string;
    }
    
    onChange(newValue) {
        this.props.record.update({ [this.props.name]: newValue });
    }
}

export const ikeCheckboxField = {
    component: IkeCheckboxField,
    displayName: "Ike Checkbox",
    supportedTypes: ["boolean"],
    additionalClasses: ["o_ike_checkbox_field"],
};

registry.category("fields").add("ike_checkbox_radio", ikeCheckboxField);
