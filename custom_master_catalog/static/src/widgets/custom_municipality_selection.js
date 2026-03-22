import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { m2oTupleFromData } from "@web/views/fields/many2one/many2one_field";
import { useSelectCreate } from "@web/views/fields/relational_utils";

import { Component, onWillStart, useState } from "@odoo/owl";

class CustomMunicipalitySelection extends Component {
    static template = "custom_master_catalog.CustomMunicipalitySelection";
    static props = {
        ...standardWidgetProps,
        fieldName: String,
    };
    static defaultProps = {
    };
    static components = { Many2XAutocomplete };

    setup() {
        // console.log("CustomMunicipalitySelectionWidget", this);

        this.orm = useService("orm");
        this.state = useState({
            countryId: null,
            stateId: null,
        });

        const selectCreate = useSelectCreate({
            resModel: "custom.state.municipality",
            activeActions: {
                create: false,
                createEdit: false,
                delete: false,
                edit: false,
                link: true,
                unlink: true,
                write: false,
            },
            onSelected: (resIds) => this.selectMunicipalityRecords(resIds),
            onCreateEdit: () => this.createOpenRecord(),
        });

        this.selectCreate = (params) => {
            return selectCreate(params);
        };

        onWillStart(async () => {
            this.orm.searchRead("res.country",
                [["code", "=", "MX"]],
                ["id", "name"]
            ).then(mx => {
                this.state.countryId = [mx[0].id, mx[0].name];
            });
        });
    }

    /** Main Select */
    async selectMunicipalityRecords(resIds) {
        if (resIds.length) {
            const areas = resIds.map(id => ({
                parent_id: this.props.record.data.id,
                country_id: this.state.countryId ? this.state.countryId[0] : null,
                state_id: this.state.stateId ? this.state.stateId[0] : null,
                municipality_id: id,
            }));

            for (const area of areas) {
                const area_id = await this.props.record.data[this.props.fieldName].addNewRecord({
                    context: {
                        default_parent_id: area.parent_id,
                        default_country_id: area.country_id,
                        default_state_id: area.state_id,
                        default_municipality_id: area.municipality_id,
                        default_widget_pending: true,
                    },
                });
                for (let productId of this.productIds) {
                    await area_id.data.area_product_ids.addNewRecord({
                        context: {
                            default_geographical_area_id: area_id.data.id,
                            default_product_id: productId,
                            default_active: true,
                        },
                    });
                }
            }
        }
    }

    /** Events */
    onSelectMunicipalities() {
        const title = _t("Municipalities");
        const context = {};
        const domain = [
            ['id', 'not in', this.resIds],
            ['disabled', '=', false],
        ];
        if (this.state.countryId) {
            domain.push(['country_id', '=', this.state.countryId[0]]);
        }
        if (this.state.stateId) {
            domain.push(['state_id', '=', this.state.stateId[0]]);
        }

        return this.selectCreate({ domain, context, title });
    }

    /** Many2one fields */
    get countryMany2XAutocompleteProps() {
        return {
            value: this.state.countryId ? this.state.countryId[1] : "",
            id: "country_id",
            placeholder: _t("Country"),
            resModel: 'res.country',
            autoSelect: true,
            fieldString: 'Country',
            noSearchMore: true,
            activeActions: {
                create: false,
                createEdit: false,
                write: false,
            },
            update: async (value) => {
                // console.log("Many2XAutocomplete - Update", value);
                if (value) {
                    value = m2oTupleFromData(value[0]);
                }
                return this._updateCountry(value);
            },
            // quickCreate: () => { },
            // context: this.context,
            getDomain: () => [],
            // nameCreateField: 'name',
            // setInputFloats: this.setFloating,
            // autocomplete_container: this.autocompleteContainerRef,
        };
    }
    _updateCountry(value) {
        this.state.countryId = value;
    }
    get stateMany2XAutocompleteProps() {
        return {
            value: this.state.stateId ? this.state.stateId[1] : "",
            id: "state_id",
            placeholder: _t("State"),
            resModel: 'res.country.state',
            autoSelect: true,
            fieldString: 'State',
            noSearchMore: true,
            searchLimit: 32,
            activeActions: {
                create: false,
                createEdit: false,
                write: false,
            },
            update: async (value) => {
                if (value) {
                    value = m2oTupleFromData(value[0]);
                }
                return this._updateState(value);
            },
            getDomain: () => {
                if (this.state.countryId) {
                    return [['country_id', '=', this.state.countryId[0]]];
                }
                return [];
            },
        };
    }
    _updateState(value) {
        this.state.stateId = value;
    }

    /** Get  */
    get resIds() {
        return this.props.record.data[this.props.fieldName].records.map(rec => rec.data.municipality_id[0]);
    }
    get productIds() {
        return this.props.record.data['x_allowed_product_ids'].resIds.map(x => x);
    }
}

export const customMunicipalitySelection = {
    component: CustomMunicipalitySelection,
    extractProps: ({ attrs }) => ({
        fieldName: attrs.field_name,
    }),
};

registry.category("view_widgets").add("custom_municipality_selection", customMunicipalitySelection);