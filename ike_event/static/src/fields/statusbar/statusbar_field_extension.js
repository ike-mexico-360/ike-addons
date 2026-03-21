import { onWillRender, useEffect, useExternalListener, useRef } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { useCommand } from "@web/core/commands/command_hook";
import { Domain } from "@web/core/domain";
import { _t } from "@web/core/l10n/translation";
import { escape } from "@web/core/utils/strings";
import { throttleForAnimation } from "@web/core/utils/timing";
import { getFieldDomain } from "@web/model/relational_model/utils";
import { useSpecialData } from "@web/views/fields/relational_utils";
import { StatusBarField } from "@web/views/fields/statusbar/statusbar_field";
import { patch } from "@web/core/utils/patch";


patch(StatusBarField.prototype, {
    setup() {
        // Properties
        this.items = {};
        this.beforeRef = useRef("before");
        this.rootRef = useRef("root");
        this.afterRef = useRef("after");
        this.dropdownRef = useRef("dropdown");

        // Resize listeners
        let status = "idle";
        const adjust = () => {
            status = "adjusting";
            this.adjustVisibleItems();
            this.render();
            browser.requestAnimationFrame(() => (status = "idle"));
        };

        useEffect(
            () => status === "shouldAdjust" && adjust(),
            () => [status]
        );

        onWillRender(() => {
            if (status !== "adjusting") {
                Object.assign(this.items, this.getSortedItems());
                status = "shouldAdjust";
            }
        });

        useExternalListener(window, "resize", throttleForAnimation(adjust));

        // Special data
        if (this.field.type === "many2one") {
            this.setSpecialData();
        }

        // Command palette
        if (this.props.withCommand) {
            const moveToCommandName = _t("Move to %s...", escape(this.field.string));
            useCommand(
                moveToCommandName,
                () => ({
                    placeholder: moveToCommandName,
                    providers: [
                        {
                            provide: () =>
                                this.getAllItems().map((item) => ({
                                    name: item.label,
                                    action: () => this.selectItem(item),
                                })),
                        },
                    ],
                }),
                {
                    category: "smart_action",
                    hotkey: "alt+shift+x",
                    isAvailable: () => !this.props.isDisabled,
                }
            );
            useCommand(
                _t("Move to next %s", this.field.string),
                () => {
                    const items = this.getAllItems();
                    const nextIndex = items.findIndex((item) => item.isSelected) + 1;
                    this.selectItem(items[nextIndex]);
                },
                {
                    category: "smart_action",
                    hotkey: "alt+x",
                    isAvailable: () =>
                        !this.props.isDisabled && !this.getAllItems().at(-1).isSelected,
                }
            );
        }
    },
    setSpecialData(extraFieldNames = []) {
        this.specialData = useSpecialData((orm, props) => {
            const { foldField, name: fieldName, record } = props;
            const { relation } = record.fields[fieldName];
            const fieldNames = ["display_name"].concat(extraFieldNames);
            if (foldField) {
                fieldNames.push(foldField);
            }
            const value = record.data[fieldName];
            let domain = getFieldDomain(record, fieldName, props.domain);
            if (domain.length && value) {
                domain = Domain.or([[["id", "=", value[0]]], domain]).toList(
                    record.evalContext
                );
            }
            return orm.searchRead(relation, domain, fieldNames);
        });
    },
});
