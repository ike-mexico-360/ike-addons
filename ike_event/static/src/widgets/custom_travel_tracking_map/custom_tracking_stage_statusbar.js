/** @odoo-module **/
import { Component, onWillStart, onWillUnmount } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { getFieldDomain } from "@web/model/relational_model/utils";
import { useSpecialData } from "@web/views/fields/relational_utils";
import { registry } from "@web/core/registry";
import { _t } from '@web/core/l10n/translation';


export class IkeTravelTrackingStatusbar extends Component {
    static template = "ike_event.IkeTravelTrackingStatusbar";

    static props = {
        ...standardFieldProps,
        visibleSelection: { type: Array, element: String, optional: true },
        matchVisibleField: { type: String, optional: true },
    };

    setup() {
        super.setup();
        this.busService = this.env.services.bus_service;
        this.specialData = useSpecialData((orm, props) => {
            const { foldField, name: fieldName, record, matchVisibleField } = props;
            const { relation } = record.fields[fieldName];
            const fieldNames = ["display_name"];
            if (foldField) {
                fieldNames.push(foldField);
            }
            if (matchVisibleField) {
                fieldNames.push(matchVisibleField);
            }
            const value = record.data[fieldName];
            let domain = getFieldDomain(record, fieldName, props.domain);
            if (domain.length && value) {
                domain = Domain.or([[["id", "=", value[0]]], domain]).toList(
                    record.evalContext
                );
            }
            return orm.searchRead(relation, domain, fieldNames);
        });

        onWillStart(() => {
            const resId = this.props.record.resId;
            if (resId) {
                this.busChannel = `custom_ike_event_supplier_stages_${resId}`;
                this.busService.addChannel(this.busChannel);
            }
        });

        this.broadcast_update_stage = async (message) => {
            // Verificar que el mensaje sea para este registro
            const payload = message.payload || message;
            if (payload.id === this.props.record.resId) {
                // Recargar el registro completo
                await this.props.record.load();
            }
        }

        this.busService.subscribe("update_ike_event_supplier_stage", this.broadcast_update_stage);

        // Cleanup al desmontar
        onWillUnmount(() => {
            if (this.busChannel) {
                this.busService.deleteChannel(this.busChannel);
                this.busService.unsubscribe("update_ike_event_supplier_stage", this.broadcast_update_stage);
            }
        });
    }

    get field() {
        return this.props.record.fields[this.props.name];
    }

    getAllItems() {
        const { foldField, name, record, visibleSelection, matchVisibleField } = this.props;
        const currentValue = record.data[name];
        if (this.field.type === "many2one") {
            // Many2one
            return this.specialData.data
                .filter((option) => {
                    // Solo filtrar si AMBOS visibleSelection y matchVisibleField tienen valor
                    if (visibleSelection && visibleSelection.length > 0 && matchVisibleField) {
                        // Aplicar el filtrado, si el valor actual es igual al valor seleccionado o si está en visibleSelection
                        return option.id === currentValue[0] || visibleSelection.includes(option[matchVisibleField]);
                    }
                    // Si alguno no tiene valor, mostrar todas las opciones sin filtrar
                    return true;
                })
                .map((option) => ({
                    id: option.id,
                    value: option.id,
                    label: option.display_name,
                    isFolded: option[foldField],
                    isSelected: Boolean(currentValue && option.id === currentValue[0]),
                    ref: option[matchVisibleField],
                }));
        } else {
            // Selection
            let { selection } = this.field;
            if (visibleSelection?.length) {
                selection = selection.filter(
                    ([value]) => value === currentValue || visibleSelection.includes(value)
                );
            }
            return selection.map(([value, label]) => ({
                value,
                label,
                isFolded: false,
                isSelected: value === currentValue,
            }));
        }
    }

    get items() {
        return this.getAllItems();
    }
}

export const ikeTravelTrackingStatusbar = {
    component: IkeTravelTrackingStatusbar,
    additionalClasses: ["ike_travel_tracking_statusbar_container"],
    extractProps: ({ attrs, options, viewType }, dynamicInfo) => ({
        // isDisabled: !options.clickable || dynamicInfo.readonly,
        visibleSelection: attrs.statusbar_visible?.trim().split(/\s*,\s*/g),
        matchVisibleField: options.match_visible_field,
        // withCommand: viewType === "form",
        // foldField: options.fold_field,
        // domain: dynamicInfo.domain,
    }),
};

registry.category("fields").add("ike_travel_tracking_statusbar", ikeTravelTrackingStatusbar);
