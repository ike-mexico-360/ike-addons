import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { FieldLabelSectionAndNoteOne2Many, fieldLabelSectionAndNoteOne2Many } from "./field_label_section_and_note_field";
import { IkeSectionAndNoteListRender } from "./ike_section_and_note_field";

export class IkeSupplierSectionAndNoteListRender extends IkeSectionAndNoteListRender {
    static template = "ike_event.IkeSectionAndNoteListRenderer";
    getActiveColumns(list) {
        let activeColumns = super.getActiveColumns(list);
        let timerWidgetColumn = activeColumns.find(col => col.name == "ike_timer_widget");
        if (timerWidgetColumn) {
            timerWidgetColumn.label = _t("Elapsed Time");
        }
        return activeColumns;
    }
    getRowClass(record) {
        let classes = super.getRowClass(record);
        const currentState = record.data.state;
        const assignationType = record.data.assignation_type;
        const isManual = record.data.is_manual;
        if (['rejected', 'timeout', 'expired'].includes(currentState)) {
            classes += " ike-row-inactive";
        } else if (currentState == 'notified') {
            classes += " ike-row-active";
        } else if (['accepted', 'assigned'].includes(currentState)) {
            classes += " ike-row-selected";
        } else if (['cancel', 'cancel_event', 'cancel_supplier'].includes(currentState)) {
            classes += " ike-row-cancelled"
        }

        if (assignationType == 'electronic') {
            classes += " ike-row-electronic";
        } else if (assignationType == 'publication') {
            classes += " ike-row-publication";
        } else if (isManual) {
            classes += " ike-row-manual-manual";
        } else if (assignationType == 'manual') {
            classes += " ike-row-manual";
        }
        return classes;
    }
}

IkeSupplierSectionAndNoteListRender.recordRowTemplate = "ike_event.IkeSupplierSectionListRenderer.RecordRow";


export class IkeSupplierSectionAndNoteOne2Many extends FieldLabelSectionAndNoteOne2Many {
    static components = {
        ...FieldLabelSectionAndNoteOne2Many.components,
        ListRenderer: IkeSupplierSectionAndNoteListRender,
    };
    setup() {
        // console.log("IkeSectionAndNoteOne2Many", this);
        super.setup();
    }
}

export const ikeSupplierSectionAndNoteOne2Many = {
    ...fieldLabelSectionAndNoteOne2Many,
    component: IkeSupplierSectionAndNoteOne2Many,
};


registry
    .category("fields")
    .add("ike_supplier_section_and_note_field_o2m", ikeSupplierSectionAndNoteOne2Many);
