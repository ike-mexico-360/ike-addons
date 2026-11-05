import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { FieldLabelSectionAndNoteListRender, FieldLabelSectionAndNoteOne2Many, fieldLabelSectionAndNoteOne2Many } from "./field_label_section_and_note_field";


export class IkeSectionAndNoteListRender extends FieldLabelSectionAndNoteListRender {
    static template = "ike_event.IkeSectionAndNoteListRenderer";
    setup() {
        // console.log("IkeSectionAndNoteListRender", this);
        super.setup();
    }
    onClickSortColumn(column) {
        return;
    }
    uIsStorable(column) {
        return false;
    }
    /**
     * Products Filter
     */
    getFilteredRecords(list) {
        const root = this.env.model.root;
        let event_supplier_number = root.data.supplier_number || root.data.event_supplier_number;
        if (!event_supplier_number) {
            return list.records;
        }
        return list.records.filter(record =>
            (!record.data.supplier_number || record.data.supplier_number == event_supplier_number)
        );
    }
}

export class IkeSectionAndNoteOne2Many extends FieldLabelSectionAndNoteOne2Many {
    static components = {
        ...FieldLabelSectionAndNoteOne2Many.components,
        ListRenderer: IkeSectionAndNoteListRender,
    };
    setup() {
        // console.log("IkeSectionAndNoteOne2Many", this);
        super.setup();
    }
}

IkeSectionAndNoteListRender.rowsTemplate = "ike_event.IkeSectionListRenderer.Rows";
// IkeSectionAndNoteListRender.recordRowTemplate = "ike_event.IkeSectionListRenderer.RecordRow";

export const ikeSectionAndNoteOne2Many = {
    ...fieldLabelSectionAndNoteOne2Many,
    component: IkeSectionAndNoteOne2Many,
};


registry
    .category("fields")
    .add("ike_section_and_note_field_o2m", ikeSectionAndNoteOne2Many);
