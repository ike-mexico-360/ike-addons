import { _t } from "@web/core/l10n/translation";
import { ListController } from "@web/views/list/list_controller";
import { CustomConfirmationDialog } from "../confirmation_dialog/confirmation_dialog";
import { patch } from "@web/core/utils/patch";

patch(ListController.prototype, {
    setup(){
        // console.log("ListController", this);
        super.setup();
        this.disableEnabled =
            "disabled" in this.props.fields
                ? !this.props.fields.disabled.readonly
                : false;
        // Overwrite
        this.archiveEnabled &= !this.disableEnabled;
    },
    getStaticActionMenuItems() {
        let res = super.getStaticActionMenuItems();
        res = {
            ...res,
            disable: {
                isAvailable: () => this.disableEnabled,
                sequence: 10,
                description: _t("Disable"),
                icon: "fa fa-level-down",
                callback: () => {
                    this.dialogService.add(CustomConfirmationDialog, this.disableDialogProps);
                },
            },
            enable: {
                isAvailable: () => this.disableEnabled,
                sequence: 10,
                icon: "fa fa-level-up",
                description: _t("Enable"),
                callback: () => this.toggleDisableState(false),
            },
        }
        return res;
    },
    get disableDialogProps() {
        return {
            body: _t("Are you sure that you want to disable all the selected records?"),
            confirmLabel: _t("Disable"),
            confirm: (reason) => {
                this.toggleDisableState(true, reason);
            },
            cancel: () => {},
        };
    },
    /**
     * Called when clicking on 'Disable' or 'Enable' in the sidebar.
     *
     * @private
     * @param {boolean} disable
     * @returns {Promise}
     */
    async toggleDisableState(disable, reason) {
        if (disable) {
            return this.model.root.disable(true, reason);
        }
        return this.model.root.enable(true, reason);
    }
});