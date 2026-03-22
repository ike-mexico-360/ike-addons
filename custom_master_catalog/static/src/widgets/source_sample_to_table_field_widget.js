/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

import {
    Component,
    onMounted,
    onPatched,
    useRef
} from "@odoo/owl";


export class SourceSampleToTableField extends Component {
    static template = "custom_master_catalog.SourceSampleToTableField";

    static props = {
        ...standardFieldProps,
    };
    static defaultProps = {};

    setup() {
        console.log("ArrayToTableField", this);
        this.container = useRef("container");
        this.origin_type = this.props.record.data.origin_type;
        let data = this.props.record.data[this.props.name];
        this.data = [];
        this.columns = [];
        if (data.length) {
            this.data = JSON.parse(data);
            if (this.origin_type == 'web_api') {
                if (this.data.length) {
                    this.columns = Object.keys(this.data[0]);
                }
            } else {
                this.columns = this.data[0];
            }
        }

        onMounted(() => {
            if (this.container.el) {
                this.container.el.parentElement.classList.add("w-100");
            }
        });
        onPatched(() => {

        });
    }
};

export const sourceSampleToTableField = {
    component: SourceSampleToTableField,
    displayName: "Array to table field",
    supportedTypes: ["text"],
};

registry.category("fields").add("source_sample_to_table", sourceSampleToTableField);
