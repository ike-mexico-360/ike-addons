import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRecordObserver } from "@web/model/relational_model/utils";
import { FormViewDialog } from "@web/views/view_dialogs/form_view_dialog";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { ViewButton } from "@web/views/view_button/view_button";
import { BUTTON_CLICK_PARAMS } from "@web/views/utils";
import { usePopover } from "@web/core/popover/popover_hook";

import { Component, onMounted, useState, useRef } from "@odoo/owl";

const BUTTON_STRING_PROPS = ["string", "size", "title", "icon", "id", "disabled"];

export class IkeButtonCheckboxPopover extends Component {
    static props = { "*": { optional: true } };
    static template = "ike_event.IkeButtonCheckboxPopover";
};

export class IkeButtonCheckbox extends Component {
    static template = "ike_event.IkeButtonCheckbox";
    static components = { ViewButton };
    static props = {
        ...standardWidgetProps,
        className: { type: String, optional: true },
        special: { type: String, optional: true },
        context: { type: String, optional: true },
        string: { type: String, optional: true },
        title: { type: String, optional: true },
        text: { type: String, optional: true },
        confirm: { type: String, optional: true },
        hotkey: { type: String, optional: true },
    };
    static defaultProps = {
        className: "btn btn-secondary",
    };
    setup() {
        console.log("IkeButtonCheckbox", this);
        this.state = useState({ checked: false });
        this.popover = usePopover(IkeButtonCheckboxPopover, {
            position: "top",
            closeOnClickAway: () => false,
            holdOnHover: true,
        });
        this.checkboxButton = useRef("checkboxButton");
        onMounted(() => {
            if (!this.props.readonly) {
                this.showPopover();
            }
        });
    }
    get ViewButtonProps() {
        const clickParams = {
            special: this.props.special,
            type: "button",
        };
        const attrs = {};
        const props = {};
        const result = {
            record: this.props.record,
            string: this.props.string,
            className: this.props.className,
            disabled: !this.state.checked || this.props.readonly,
            clickParams,

        }
        // console.log(result)
        return result;
    }
    onClickCheckbox() {
        this.state.checked = !this.state.checked;
        this.showPopover();
    }
    showPopover() {
        if (this.props.confirm) {
            if (!this.state.checked) {
                this.popover.open(this.checkboxButton.el, {
                    title: this.props.title,
                    body: this.props.confirm,
                });
            } else {
                this.popover.close();
            }
        }
    }
};

export const ikeButtonCheckbox = {
    component: IkeButtonCheckbox,
    extractProps: ({ attrs, options }, dynamicInfo) => {
        // console.log(attrs, dynamicInfo)
        return {
            special: attrs.special,
            context: attrs.context,
            string: attrs.string,
            className: attrs.className,
            title: attrs.title,
            confirm: attrs.confirm,
            hotkey: attrs.hotkey,
        };
    },
};

registry.category("view_widgets").add("ike_button_checkbox", ikeButtonCheckbox);
