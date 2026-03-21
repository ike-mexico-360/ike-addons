import { DynamicList } from "@web/model/relational_model/dynamic_list";
import { patch } from "@web/core/utils/patch";

patch(DynamicList.prototype, {
    disable(isSelected, reason) {
        return this.model.mutex.exec(() => this._toggleDisable(isSelected, true, reason))
    },
    enable(isSelected, reason) {
        return this.model.mutex.exec(() => this._toggleDisable(isSelected, false, reason));
    },
    async _toggleDisable(isSelected, state, reason) {
        const method = state ? "action_disable" : "action_enable";
        const context = this.context;
        const resIds = await this.getResIds(isSelected);
        const action = await this.model.orm.call(this.resModel, method, [resIds], {
            context,
            reason,
        });
        if (
            this.isDomainSelected &&
            resIds.length === this.model.activeIdsLimit &&
            resIds.length < this.count
        ) {
            const msg = _t(
                "Of the %(selectedRecord)s selected records, only the first %(firstRecords)s have been disabled/enabled.",
                {
                    selectedRecords: resIds.length,
                    firstRecords: this.count,
                }
            );
            this.model.notification.add(msg, { title: _t("Warning") });
        }
        const reload = () => this.model.load();
        if (action && Object.keys(action).length) {
            this.model.action.doAction(action, {
                onClose: reload,
            });
        } else {
            return reload();
        }
    },
});
