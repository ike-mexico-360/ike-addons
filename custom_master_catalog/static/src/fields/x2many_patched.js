import { patch } from "@web/core/utils/patch";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { ListRenderer } from "@web/views/list/list_renderer";
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";


ListRenderer.props = [...ListRenderer.props, 'deleteConditionField?'];
KanbanRenderer.props = [...KanbanRenderer.props, 'deleteConditionField?'];

patch(ListRenderer.prototype, {
    isDeleteHidden(record) {
        if (!this.props.deleteConditionField) {
            return false;
        }
        if (!record || (record.isNew && record.isInEdition)) {
            return false;
        }
        const fieldCondition = this.props.deleteConditionField;
        const negate = fieldCondition.startsWith('!');
        const fieldName = negate ? fieldCondition.slice(1) : fieldCondition;
        const value = record.data[fieldName];
        return negate ? !value : value;
    }
});


patch(X2ManyField, {
    props: {
        ...X2ManyField.props,
        deleteConditionField: { type: String, optional: true },
    },
});

patch(X2ManyField.prototype, {
    get rendererProps() {
        return {
            ...super.rendererProps,
            deleteConditionField: this.props.deleteConditionField,
        }
    },
});

const patchX2ManyField = () => ({
    extractProps({ options }) {
        const props = super.extractProps(...arguments);
        props.deleteConditionField = options.delete_condition_field;
        return props;
    },
    supportedOptions: [{
        label: "Delete Condition Field",
        name: "delete_condition_field",
        type: "string",
        default: null,
    }],
});

patch(x2ManyField, patchX2ManyField());
