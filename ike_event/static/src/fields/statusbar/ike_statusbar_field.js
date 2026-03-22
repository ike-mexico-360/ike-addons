import { statusBarDurationField, StatusBarDurationField } from "@mail/views/fields/statusbar_duration/statusbar_duration_field";
import { formatDuration } from "@web/core/l10n/dates";
import { registry } from "@web/core/registry";


export class IkeStatusBarDurationField extends StatusBarDurationField {
    setup() {
        super.setup();
        // console.log("ike_statusbar", this);
    }
    setSpecialData() {
        super.setSpecialData(["last_stage", "color"]);
    }

    adjustVisibleItems() { }

    getSortedItems() {
        let result = super.getSortedItems();
        result.inlineReverse = result.inline.reverse();
        const current = result.inline.find(item => item.isSelected);
        if (current && current.lastStage) {
            result.inlineReverse = result.inlineReverse.filter(item => item.fullTimeInStage);
        }
        return result;
    }

    getAllItems() {
        const { foldField, name, record } = this.props;
        const currentValue = record.data[name];
        const durationTracking = this.props.record.data.duration_tracking || {};
        const items = this.specialData.data.map((option) => {
            const duration = durationTracking[option.id];
            let shortTimeInStage = 0;
            let fullTimeInStage = null;
            if (duration > 0) {
                shortTimeInStage = formatDuration(duration, false);
                fullTimeInStage = formatDuration(duration, true);
            }

            return {
                value: option.id,
                label: option.display_name,
                isFolded: option[foldField],
                lastStage: option['last_stage'],
                color: option['color'],
                isSelected: Boolean(currentValue && option.id === currentValue[0]),
                shortTimeInStage: shortTimeInStage,
                fullTimeInStage: fullTimeInStage,
            }
        });
        return items;
    }

    async selectItem(item) {
        if (this.props.isDisabled) {
            return;
        }
        super.selectItem(item);
    }
}

IkeStatusBarDurationField.template = "ike_event.IkeStatusBarDurationField";

export const ikeStatusBarDurationField = {
    ...statusBarDurationField,
    component: IkeStatusBarDurationField,
}

registry.category("fields").add("ike_statusbar_duration", ikeStatusBarDurationField);
