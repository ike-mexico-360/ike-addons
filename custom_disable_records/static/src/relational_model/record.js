import { Record } from "@web/model/relational_model/record";
import { patch } from "@web/core/utils/patch";

patch(Record.prototype, {
    get isDisabled() {
        if ("disabled" in this.activeFields) {
            return this.data.disabled;
        }
        return false;
    },
    disable(reason) {
        return this.model.mutex.exec(() => this._toggleDisable(true, reason))
    },
    enable(reason) {
        return this.model.mutex.exec(() => this._toggleDisable(false, reason));
    },
    async _toggleDisable(state, reason) {
        const method = state ? "action_disable" : "action_enable";
        const action = await this.model.orm.call(this.resModel, method, [[this.resId]], {
            context: this.context,
            reason: reason,
        });
        if (action && Object.keys(action).length) {
            this.model.action.doAction(action, { onClose: () => this._load() });
        } else {
            return this._load();
        }
    }
});
