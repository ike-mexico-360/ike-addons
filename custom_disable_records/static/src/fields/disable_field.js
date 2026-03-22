import { _t } from "@web/core/l10n/translation";
import { BooleanField, booleanField } from "@web/views/fields/boolean/boolean_field";
import { CustomConfirmationDialog } from "../confirmation_dialog/confirmation_dialog";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";

export class DisableField extends BooleanField {
    setup() {
        // console.log("DisableField", this);
        super.setup();
        this.dialogService = useService("dialog");
    }
    onChange(newValue) {
        if (newValue && (this.props.disabledReasonAction || this.props.disabledReasonField)) {
            this.dialogService.add(CustomConfirmationDialog, this.disableDialogProps);
        } else {
            this.state.value = newValue;
            this.props.record.update({ [this.props.name]: newValue });
        }
    }
    get disableDialogProps() {
        return {
            body: _t("Are you sure that you want to disable this record?"),
            confirmLabel: _t("Disable"),
            confirm: async (reason) => {
                if (this.props.disabledReasonField) {
                    this.state.value = true;
                    await this.props.record.update({
                        [this.props.name]: true,
                        [this.props.disabledReasonField]: reason,
                    });
                }
                if (this.props.disabledReasonAction) {
                    this.props.record.disable(user.name + ": " + reason);
                }
            },
            cancel: () => { },
        };
    }
}

DisableField.props = {
    ...BooleanField.props,
    disabledReasonAction: { type: Boolean, optional: true },
    disabledReasonField: { type: String, optional: true },
};
DisableField.defaultProps = {
    ...BooleanField.defaultProps,
    disabledReasonAction: true,
    disabledReasonField: null,
}

export const disableField = {
    ...booleanField,
    component: DisableField,
    supportedOptions: [
        {
            label: _t("Disabled Reason Field"),
            name: "disabled_reason_field",
            type: "string",
            help: _t(
                "If is not null or empty, write this field name with the disabled reason."
            )
        },
        {
            label: _t("Disable Reason Action"),
            name: "disabled_reason_action",
            type: "boolean",
            help: _t(
                "If checked, execute action_disable global function."
            ),
        },
    ],
    extractProps({ options, attrs }) {
        const disabledReasonAction = options.disabled_reason_action != null ? Boolean(options.disabled_reason_action) : true;
        const disabledReasonField = options.disabled_reason_field;

        return {
            disabledReasonAction,
            disabledReasonField,
        };
    },
};

registry.category("fields").add("disable_field", disableField);
