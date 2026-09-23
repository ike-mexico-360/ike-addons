import { RadioField, radioField } from "@web/views/fields/radio/radio_field";
import { registry } from "@web/core/registry";
import { getFieldDomain } from "@web/model/relational_model/utils";
import { useSpecialData } from "@web/views/fields/relational_utils";

let nextId = 0;
export class IkeServiceRadioField extends RadioField {
    setup() {
        // console.log("IkeServiceRadio", this);
        this.id = `radio_field_${nextId++}`;
        this.type = this.props.record.fields[this.props.name].type;
        if (this.type === "many2one") {
            this.specialData = useSpecialData(async (orm, props) => {
                const { relation } = props.record.fields[props.name];
                const domain = getFieldDomain(props.record, props.name, props.domain);
                const kwargs = {
                    specification: { display_name: 1, [this.props.iconField]: {} },
                    domain,
                };
                const { records } = await orm.call(relation, "web_search_read", [], kwargs);
                return records.map((record) => [record.id, record.display_name, record[this.props.iconField]]);
            });
        }
    }
    get label() {
        return this.props.record.fields[this.props.name].string;
    }
}

IkeServiceRadioField.template = "ike_event.IkeServiceRadioField";
IkeServiceRadioField.props = {
    ...RadioField.props,
    iconField: { type: String, optional: true },
};
IkeServiceRadioField.defaultProps = {
    ...RadioField.defaultProps,
    iconField: "icon",
};

export const ikeServiceRadioField = {
    ...radioField,
    component: IkeServiceRadioField,
    extractProps({ options }) {
        const props = radioField.extractProps(...arguments);
        props.iconField = options.icon_field;
        return props;
    },
}

registry.category("fields").add("ike_service_radio", ikeServiceRadioField);
