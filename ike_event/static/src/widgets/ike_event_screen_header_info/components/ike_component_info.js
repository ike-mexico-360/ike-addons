/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps, onMounted, onPatched, useRef, markup } from "@odoo/owl";
import { Record } from "@web/model/record";
import { Field, getFieldFromRegistry } from "@web/views/fields/field";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";


export class IkeComponentInfo extends Component {
    static template = "ike_event.IkeComponentInfo";
    static components = { Record, Field };
    static props = {
        ...standardWidgetProps,
        maxHeight: { type: Number, optional: true },
        orientation: { type: String, optional: true },
        fieldName: { type: String, optional: false },
        record: { type: Object, optional: false },
    };
    static defaultProps = {
        orientation: "vertical",
        maxHeight: 120,
    };

    setup() {
        this.fieldsContentRef = useRef("fieldsContent");

        this.state = useState({
            isLoading: true,
            recordKey: 0,
            isExpanded: false,
            hasMoreLines: false
        });

        onWillStart(async () => {
            // Dar tiempo para que Record se inicialice
            await Promise.resolve();
            this.state.isLoading = false;
        });

        onWillUpdateProps(async (nextProps) => {
            // Incrementar la clave para forzar re-creación del Record
            this.state.recordKey++;
        });

        onMounted(() => {
            this.checkLineCount();
        });

        onPatched(() => {
            if (!this.state.isLoading) {
                this.checkLineCount();
            }
        });
    }

    // Botón mostrar más, mostrar menos
    checkLineCount() {
        const el = this.fieldsContentRef.el;
        if (!el || this.fieldsList.length === 0) {
            this.state.hasMoreLines = false;
            return;
        }

        const fullHeight = el.scrollHeight;
        if (fullHeight <= 0) return;

        if (fullHeight > this.props.maxHeight && this.props.orientation === 'vertical') {
            this.state.hasMoreLines = true;
            if (!this.state.isExpanded) {
                this.updateMaxHeight();
            }
        } else {
            this.state.hasMoreLines = false;
            el.style.maxHeight = '';
        }
    }
    showMore() {
        this.state.isExpanded = !this.state.isExpanded;
        this.updateMaxHeight();
    }
    updateMaxHeight() {
        const el = this.fieldsContentRef.el;
        if (!el) return;

        if (this.state.isExpanded) {
            el.style.maxHeight = `${el.scrollHeight}px`;
        } else {
            el.style.maxHeight = `${this.props.maxHeight}px`;
        }
    }
    get buttonText() {
        return this.state.isExpanded ? _t("Show Less") : _t("Show More");
    }

    // Generar una clave única basada en los campos
    get recordKey() {
        // Usar la clave del estado + hash de los nombres de campos
        const fieldsHash = this.fieldsList.map(f => f.name).join(',');
        return `${this.state.recordKey}-${fieldsHash}`;
    }

    get data() {
        return this.props.record.data;
    }

    get existField() {
        if (this.props.fieldName === undefined || this.props.fieldName === "" || this.props.fieldName === null) {
            return false;
        }
        return this.data[this.props.fieldName] !== undefined ? true : false;
    }

    get virtualModel() {
        return 'ike.event.summary_virtual'
    }

    // Obtener los datos del campo JSON de forma reactiva
    get jsonFieldData() {
        const jsonData = this.props.record.data[this.props.fieldName];

        if (!jsonData) {
            return null;
        }

        // Si es string, parsearlo
        if (typeof jsonData === 'string') {
            try {
                return JSON.parse(jsonData);
            } catch (e) {
                console.error('Error parsing JSON:', e);
                return null;
            }
        }

        // Si ya es objeto, retornarlo directamente
        return jsonData;
    }

    get title() {
        const title = this.jsonFieldData?.title || '';
        if (typeof title === 'string') {
            return markup(title);
        }
        return title;
    }

    get fieldsList() {
        return this.jsonFieldData?.fields || [];
    }

    // Crear la estructura completa de fields para Record
    get virtualFields() {
        if (!this.jsonFieldData || !this.fieldsList.length) {
            return {};
        }

        const fields = {};

        this.fieldsList.forEach(field => {
            const fieldDef = {
                type: field.type,
                string: field.string || field.name,
                readonly: true,
                required: false,
                store: false,
            };

            // Propiedades específicas según el tipo de campo
            switch (field.type) {
                case 'many2one':
                    if (field.relation) {
                        fieldDef.relation = field.relation;
                    }
                    break;

                case 'many2many':
                case 'one2many':
                    if (field.relation) {
                        fieldDef.relation = field.relation;
                    }
                    break;

                case 'selection':
                    if (field.selection) {
                        fieldDef.selection = field.selection;
                    }
                    break;

                case 'float':
                    if (field.digits) {
                        fieldDef.digits = field.digits;
                    }
                    break;

                case 'monetary':
                    if (field.digits) {
                        fieldDef.digits = field.digits;
                    }
                    if (field.currency_field) {
                        fieldDef.currency_field = field.currency_field;
                    }
                    break;
            }

            fields[field.name] = fieldDef;
        });

        return fields;
    }

    // Crear activeFields para Record
    get virtualActiveFields() {
        if (!this.jsonFieldData || !this.fieldsList.length) {
            return {};
        }

        const activeFields = {};

        this.fieldsList.forEach(field => {
            const activeField = {
                attrs: {},
                options: {},
                domain: "[]",
                string: field.string || field.name,
            };

            // Widget personalizado si viene en el JSON
            if (field.widget) {
                activeField.widget = field.widget;
            }

            // Opciones personalizadas si vienen en el JSON
            if (field.options) {
                activeField.options = { ...field.options };
            }

            activeFields[field.name] = activeField;
        });

        return activeFields;
    }

    // Crear values (los datos reales)
    get virtualValues() {
        if (!this.jsonFieldData || !this.fieldsList.length) {
            return {};
        }

        const values = {};

        this.fieldsList.forEach(field => {
            let value = field.value;

            // Conversión de valores según el tipo
            if (field.type === 'many2one') {
                if (Array.isArray(value) && value.length >= 2) {
                    value = {
                        id: value[0],
                        display_name: value[1]
                    };
                } else if (typeof value === 'number') {
                    value = value;
                } else if (value && typeof value === 'object') {
                    value = value;
                } else {
                    value = false;
                }
            }
            else if (field.type === 'many2many' || field.type === 'one2many') {
                if (Array.isArray(value) && value.length > 0) {
                    if (Array.isArray(value[0])) {
                        value = value.map(v => ({
                            id: v[0],
                            display_name: v[1]
                        }));
                    }
                } else {
                    value = [];
                }
            }
            else if (field.type === 'datetime' || field.type === 'date') {
                value = value || false;
            }
            else if (field.type === 'boolean') {
                value = Boolean(value);
            }
            else if (field.type === 'integer') {
                value = value ? parseInt(value, 10) : 0;
            }
            else if (field.type === 'float' || field.type === 'monetary') {
                value = value ? parseFloat(value) : 0.0;
            }

            values[field.name] = value;
        });

        return values;
    }

    // Crear fieldInfo para cada campo (usado por Field component)
    getFieldInfo(fieldDef) {
        const fieldType = fieldDef.type;
        const widget = fieldDef.widget || null;

        // Obtener el componente del registry
        const field = getFieldFromRegistry(fieldType, widget);

        const fieldInfo = {
            name: fieldDef.name,
            type: fieldType,
            string: fieldDef.string || fieldDef.label || fieldDef.name,
            widget: widget,
            field: field,
            options: {},
            attrs: {},
            context: "{}",
            help: undefined,
            onChange: false,
            forceSave: false,
            decorations: {},
            readonly: "True",
            required: "False",
            invisible: "False",
            column_invisible: "False",
        };

        // Propiedades adicionales según el tipo
        if (fieldType === 'many2one' || fieldType === 'many2many' || fieldType === 'one2many') {
            if (fieldDef.relation) {
                fieldInfo.relation = fieldDef.relation;
            }
        }

        if (fieldType === 'selection' && fieldDef.selection) {
            fieldInfo.selection = fieldDef.selection;
        }

        // Opciones del JSON
        if (fieldDef.options) {
            fieldInfo.options = { ...fieldDef.options };
        }

        // relatedFields si el field lo requiere
        if (field.relatedFields) {
            let relatedFields = field.relatedFields;
            if (relatedFields instanceof Function) {
                relatedFields = relatedFields(fieldInfo);
            }
            fieldInfo.relatedFields = Object.fromEntries(
                relatedFields.map((f) => [f.name, f])
            );
        }

        return fieldInfo;
    }

    get hasValidData() {
        return this.jsonFieldData &&
               this.fieldsList.length > 0 &&
               this.existField &&
               Object.keys(this.virtualFields).length > 0;
    }
}

export const ikeEventScreenHeaderInfoIndividualComponent = {
    component: IkeComponentInfo,
    extractProps(fieldInfo, dynamicInfo) {
        return {
            fieldName: fieldInfo.attrs.fname_info,
            maxHeight: fieldInfo.options.max_height,
        };
    },
};

registry.category("view_widgets").add("ike_event_screen_header_info_individual_component", ikeEventScreenHeaderInfoIndividualComponent);
