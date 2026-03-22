import { registry } from "@web/core/registry";
import { Many2ManyCheckboxesField, many2ManyCheckboxesField } from "@web/views/fields/many2many_checkboxes/many2many_checkboxes_field";

export class IkeMany2ManyCheckboxesField extends Many2ManyCheckboxesField {
    static template = "ike_event.IkeMany2ManyCheckboxesField";

    onChange(resId, checked) {
        checked = checked.target.checked;
        super.onChange(resId, checked);
    }
}

export const ikeMany2ManyCheckboxesField = {
    ...many2ManyCheckboxesField,
    component: IkeMany2ManyCheckboxesField,
    additionalClasses: ["o_ike_checkboxes_field"],
};

registry.category("fields").add("ike_many2many_checkboxes", ikeMany2ManyCheckboxesField);
