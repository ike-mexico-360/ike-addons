import { registry } from "@web/core/registry";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";

import { Component } from "@odoo/owl";


export class IkeEventSupplierProducts extends Component {
    static template = "ike_event.IkeEventSupplierProducts";
    static props = {
        ...standardWidgetProps,
    };
    static defaultProps = {
    };
    setup() {
        console.log("IkeEventSupplierProducts setup", this);
        super.setup();
    }
}

export const ikeEventSupplierProducts = {
    component: IkeEventSupplierProducts,
    extractProps: ({ attrs, options }, dynamicInfo) => {
        // console.log("extractProps", attrs, options, dynamicInfo);
        return {
        }
    },
};

registry.category("view_widgets").add("ike_event_supplier_products", ikeEventSupplierProducts);
