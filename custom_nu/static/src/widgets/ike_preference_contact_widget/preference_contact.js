/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class PreferenceContactWidget extends Component {
    static template = "ike_event.PreferenceContactWidget";

    static props = {
        ...standardFieldProps,
    };

    setup() {
        const fieldInfo = this.props.record.fields[this.props.name];
        const selection = fieldInfo?.selection || [];
        const isRelated = Boolean(fieldInfo?.related);

        const ICONS = {
            whatsapp: "fa fa-whatsapp",
            message: "fa fa-comments",
            email: "fa fa-envelope",
        };

        // Partimos SIEMPRE del selection real
        let options = selection.map(([value]) => ({
            value,
            icon: ICONS[value] || "fa fa-circle",
        }));

        // Si es related → ocultar email
        if (isRelated) {
            options = options.filter(opt => opt.value !== "email");
        }

        this.options = options;
    }

    onSelect(ev) {
        if (this.props.readonly) {
            return;
        }
        const val = ev.currentTarget.dataset.value;
        this.props.record.update({ [this.props.name]: val });
    }
}

registry.category("fields").add("preference_contact_widget", {
    component: PreferenceContactWidget,
    supportedTypes: ["selection"],
});
