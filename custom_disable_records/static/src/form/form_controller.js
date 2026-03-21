import { _t } from "@web/core/l10n/translation";
import { FormController } from "@web/views/form/form_controller";
import { CustomConfirmationDialog } from "../confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";

patch(FormController.prototype, {
    setup() {
        // console.log("FormController", this);
        super.setup();
    },
    getStaticActionMenuItems() {
        let res = super.getStaticActionMenuItems();
        res = {
            ...res,
            disable: {
                isAvailable: () => this.disableEnabled && !this.model.root.isDisabled,
                sequence: 9,
                description: _t("Disable"),
                icon: "fa fa-level-down",
                callback: () => {
                    this.dialogService.add(CustomConfirmationDialog, this.disableDialogProps);
                },
            },
            enable: {
                isAvailable: () => this.disableEnabled && this.model.root.isDisabled,
                sequence: 9,
                icon: "fa fa-level-up",
                description: _t("Enable"),
                callback: () => this.model.root.enable(false),
            },
        }
        return res;
    },
    get disableDialogProps() {
        return {
            body: _t("Are you sure that you want to disable this record?"),
            confirmLabel: _t("Disable"),
            confirm: (reason) => {
                this.model.root.disable(reason);
            },
            cancel: () => { },
        };
    },
    get disableEnabled() {
        return "disabled" in this.model.root.activeFields
            ? !this.props.fields.disabled.readonly
            : false;
    },
    /** Overwrite */
    get archiveEnabled() {
        let res = "active" in this.model.root.activeFields
            ? !this.props.fields.active.readonly
            : "x_active" in this.model.root.activeFields
                ? !this.props.fields.x_active.readonly
                : false;

        return res && !this.disableEnabled;
    }
});