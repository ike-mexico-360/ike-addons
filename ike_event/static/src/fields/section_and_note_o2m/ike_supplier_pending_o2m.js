import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import {
    IkeSupplierSectionAndNoteListRender,
    ikeSupplierSectionAndNoteOne2Many,
    IkeSupplierSectionAndNoteOne2Many
} from "./ike_supplier_section_and_note_field";


export function getPendingGroup(record) {
    if (record.data.assignation_type === "electronic") {
        return { key: "electronic", sequence: 1, label: _t("Pending services · Electronic") };
    }
    const priorities = {
        "3": { sequence: 2, label: _t("Pending services · Publication – High priority") },
        "2": { sequence: 3, label: _t("Pending services · Publication – Medium priority") },
        "1": { sequence: 4, label: _t("Pending services · Publication – Low priority") },
    };
    const priority = priorities[record.data.priority] ? record.data.priority : "1";
    return { key: `publication_${priority}`, ...priorities[priority] };
}

function computePendingLines(records, eventData) {
    const grouped = [];
    for (const record of records) {
        grouped.push({ record, group: getPendingGroup(record) });
    }
    grouped.sort((a, b) =>
        (a.group.sequence - b.group.sequence)
        || (a.record.data.sequence - b.record.data.sequence)
        || (a.record.resId - b.record.resId)
    );
    return grouped;
}

export class IkeSupplierPendingListRenderer extends IkeSupplierSectionAndNoteListRender {
    getFilteredRecords(list) {
        this._pendingSectionLabels = new Map();
        const root = this.env.model.root;
        if (root.resModel !== "ike.event") {
            return list.records;
        }
        let event_supplier_number = root.data.supplier_number;

        const pendingRecords = list.records.filter(record =>
            record.data.second_notification
            && (!record.data.event_supplier_number || record.data.event_supplier_number == event_supplier_number)
        );

        const grouped = computePendingLines(pendingRecords, root.data);

        let lastKey = null;
        for (const { record, group } of grouped) {
            if (group.key !== lastKey) {
                this._pendingSectionLabels.set(record.id, group.label);
                lastKey = group.key;
            }
        }
        return grouped.map(group => group.record);
    }
    getPendingSectionLabel(record) {
        return this._pendingSectionLabels?.get(record.id) || false;
    }
}
IkeSupplierPendingListRenderer.recordRowTemplate = "ike_event.IkeSupplierPendingListRenderer.RecordRow";

export class IkeSupplierPendingField extends IkeSupplierSectionAndNoteOne2Many {
    static components = {
        ...IkeSupplierSectionAndNoteOne2Many.components,
        ListRenderer: IkeSupplierPendingListRenderer,
    };
    setup() {
        // console.log("IkeSupplierPendingField", this);
        super.setup();
    }
    get showTable() {
        const record = this.props.record;
        if (record.resModel !== "ike.event") {
            return true;
        }
        const supplier_number = record.data.supplier_number;
        const records = this.list.records.filter(record =>
            !record.data.display_type
            && record.data.supplier_number == supplier_number
            && record.data.second_notification
        );
        return ["manual", "manual_manual"].includes(record.data.supplier_search_type) && records.length > 0;
    }
}

IkeSupplierPendingField.template = "ike_event.IkeSupplierPendingField";

export const ikeSupplierPendingField = {
    ...ikeSupplierSectionAndNoteOne2Many,
    component: IkeSupplierPendingField,
};

registry
    .category("fields")
    .add("ike_supplier_pending_o2m", ikeSupplierPendingField);
