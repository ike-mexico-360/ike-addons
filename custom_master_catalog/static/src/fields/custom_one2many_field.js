
import { Domain } from "@web/core/domain";
import { registry } from "@web/core/registry";
import { getFieldDomain } from "@web/model/relational_model/utils";

import { Many2OneField, many2OneField } from "@web/views/fields/many2one/many2one_field";

export class CustomMany2OneFieldExclude extends Many2OneField {
    static props = {
        ...Many2OneField.props, 
        parentFieldName: { type: String, optional: true },
    }
    getDomain() {
        let domain = getFieldDomain(this.props.record, this.props.name, this.props.domain);
        let siblings = this.getSiblings();
        if (siblings) {
            domain = Domain.and([
                domain,
                [
                    ['id', 'not in', siblings.map(item => item.data[this.props.name][0])],
                ]
            ]).toList();
        }

        return domain;
    }
    getSiblings() {
        const record = this.props.record;
        const parent = record._parentRecord;
        if (!parent) return null;

        if (this.props.parentFieldName) {
            const list = parent.data[this.props.parentFieldName];
            if (list?.records?.includes(record)) {
                return list.records.filter(item => item != record && item.data[this.props.name]);
            }
        } else {
            for (const fieldName in parent.activeFields) {
                const fieldDef = parent.fields[fieldName];
                if (
                    fieldDef
                    && (fieldDef.type === "one2many" || fieldDef.type === "many2many")
                    && fieldDef.relation === record.resModel
                ) {
                    const list = parent.data[fieldName];
                    if (list?.records?.includes(record)) {
                        return list.records.filter(item => item != record && item.data[this.props.name]);
                    }
                }
            }
        }

        return null;
    }
}
export const customMany2OneFieldExclude = {
    ...many2OneField,
    component: CustomMany2OneFieldExclude,
    extractProps({ attrs, context, decorations, options, string }, dynamicInfo) {
        return {
            ...many2OneField.extractProps(...arguments),
            parentFieldName: options.parent_field_name,
        }
    },
}
registry.category("fields").add("list.custom_many2one_exclude", customMany2OneFieldExclude);