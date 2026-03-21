import { IntegerField, integerField } from "@web/views/fields/integer/integer_field";
import { registry } from "@web/core/registry";

export class IkeIntegerField extends IntegerField {
    static template = "ike_event.IkeIntegerField";

    get label() {
        return this.props.placeholder || this.props.record.fields[this.props.name].string;
    }
}

export const ikeIntegerField = {
    ...integerField,
    component: IkeIntegerField,
};

registry.category("fields").add("ike_integer", ikeIntegerField);
