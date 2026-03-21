import { Many2OneField, many2OneField } from "@web/views/fields/many2one/many2one_field";
import { registry } from "@web/core/registry";


export class IkeMany2oneField extends Many2OneField {
    static template = "ike_event.IkeMany2oneField";

    get Many2XAutocompleteProps() {
        const props = super.Many2XAutocompleteProps;
        props.placeholder = " ";
        return props;
    }

    get label() {
        return (this.props.placeholder || this.props.record.fields[this.props.name].string) + ":";
    }
}

export const ikeMany2oneField = {
    ...many2OneField,
    component: IkeMany2oneField,
}

registry.category("fields").add("ike_many2one", ikeMany2oneField);