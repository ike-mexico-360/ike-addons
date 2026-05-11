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
    isHiddenRecord(record = null) {
        if (!record || (record.isNew && record.isInEdition)) {
            return false;
        }
        let event_search_number = 1;
        if (this.env.model.root.resModel == "ike.event") {
            event_search_number = this.env.model.root.data.supplier_search_number;
        } else {
            event_search_number = record.data.event_search_number;
        }
        return (
            record.data.event_search_number && record.data.search_number != event_search_number
            || record.data.event_supplier_number && record.data.event_supplier_number != record.data.supplier_number
        );
    }
}

IkeSectionAndNoteListRender.recordRowTemplate = "ike_event.IkeSectionListRenderer.RecordRow";


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

export const ikeSectionAndNoteOne2Many = {
    ...fieldLabelSectionAndNoteOne2Many,
    component: IkeSectionAndNoteOne2Many,
};


registry
    .category("fields")
    .add("ike_section_and_note_field_o2m", ikeSectionAndNoteOne2Many);
