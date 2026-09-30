/** @odoo-module **/

import { booleanField, BooleanField } from "@web/views/fields/boolean/boolean_field";
import { registry } from "@web/core/registry";

let nextId = 0;

export class RadioBoolean extends BooleanField{
    static template = "custom_master_catalog.RadioBooleanField";
    static props = {
        ...BooleanField.props,
        orientation: { type: String, optional: true },
    };
    static defaultProps = {
        orientation: "vertical",
    };

    setup(){
        super.setup(...arguments);
        this.id = `ike_radio_boolean_field_${nextId++}`;
    }
}

export const radioBoolean = {
    ...booleanField,
    component: RadioBoolean,
    extractProps: ({ options, string }, dynamicInfo) => ({
        orientation: options.horizontal ? "horizontal" : "vertical",
    }),
};

registry.category("fields").add("radio_boolean", radioBoolean);