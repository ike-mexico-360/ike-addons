import { SelectionField, selectionField } from "@web/views/fields/selection/selection_field";
import { registry } from "@web/core/registry";

export class IkeSelectionField extends SelectionField {
    static template = "ike_event.IkeSelectionField";

    get label() {
        return this.props.placeholder || this.props.record.fields[this.props.name].string;
    }
}

export const ikeSelectionField = {
    ...selectionField,
    component: IkeSelectionField,
};

registry.category("fields").add("ike_selection", ikeSelectionField);
