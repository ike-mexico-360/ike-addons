import { ProductLabelSectionAndNoteField, productLabelSectionAndNoteField, ProductLabelSectionAndNoteListRender } from "@account/components/product_label_section_and_note_field/product_label_section_and_note_field";
import { sectionAndNoteFieldOne2Many } from "@account/components/section_and_note_fields_backend/section_and_note_fields_backend";
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";


export class FieldLabelSectionAndNoteListRender extends ProductLabelSectionAndNoteListRender {
    static props = [
        ...ProductLabelSectionAndNoteListRender.props,
        "fieldColumns?"
    ];
    static defaultProps = {
        ...ProductLabelSectionAndNoteListRender.defaultProps,
        fieldColumns: ["product_id"],
    };
    setup() {
        // console.log("SupplierLabelSectionAndNoteListRender", this);
        super.setup();
        this.productColumns = this.props.fieldColumns;
    }
}

export class FieldLabelSectionAndNoteOne2Many extends X2ManyField {
    static props = {
        ...X2ManyField.props,
        fieldColumns: { type: Object, optional: true },
    }
    static components = {
        ...X2ManyField.components,
        ListRenderer: FieldLabelSectionAndNoteListRender,
    };

    get rendererProps() {
        let props = super.rendererProps;
        props.fieldColumns = this.props.fieldColumns;
        return props;
    }
}

export const fieldLabelSectionAndNoteOne2Many = {
    ...x2ManyField,
    component: FieldLabelSectionAndNoteOne2Many,
    additionalClasses: sectionAndNoteFieldOne2Many.additionalClasses,
    extractProps: (
        { attrs, relatedFields, viewMode, views, widget, options, string },
        dynamicInfo
    ) => {
        const x2ManyFieldProps = x2ManyField.extractProps(
            { attrs, relatedFields, viewMode, views, widget, options, string },
            dynamicInfo
        );
        return {
            ...x2ManyFieldProps,
            fieldColumns: options.field_columns,
        };
    },
};


registry
    .category("fields")
    .add("field_label_section_and_note_field_o2m", fieldLabelSectionAndNoteOne2Many);


// Field
export class IkeLabelSectionAndNoteField extends ProductLabelSectionAndNoteField {
    get sectionAndNoteIsReadonly() {
        return this.props.readonly;
    }
    get Many2XAutocompleteProps() {
        const props = super.Many2XAutocompleteProps;
        props.placeholder = this.props.placeholder;
        return props;
    }
};

export const ikeLabelSectionAndNoteField = {
    ...productLabelSectionAndNoteField,
    component: IkeLabelSectionAndNoteField,
};
registry
    .category("fields")
    .add("ike_label_section_and_note_field", ikeLabelSectionAndNoteField);
