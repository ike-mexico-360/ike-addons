/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { IkeEventListButtons } from "./ike_event_list_buttons";

const STAGE_LIST = [
    'draft',
    'capturing',
    'searching',
    'assigned',
    'in_progress',
    'completed',
    'verifying',
    'closed',
    'cancel',
]

export class IkeEventScreenListRenderer extends ListRenderer {
    static template = "ike_event.IkeEventScreenListRenderer";
    static components = {
        ...ListRenderer.components,
        IkeEventListButtons,
    }

    getRowClass(record) {
        let rowClasses = super.getRowClass(record);

        const stageRef = record.data.stage_ref;
        if (STAGE_LIST.includes(stageRef)) {
            const rowClassName = `bg-list-ike-event__${stageRef}`;
            rowClasses += ` ${rowClassName}`;
        }

        return rowClasses;
    }

    getCellClass(column, record) {
        let cellClasses = super.getCellClass(column, record);
        const { name, widget } = column;
        if (widget !== undefined && widget === "badge" && name === "stage_id") {
            const stageRef = record.data.stage_ref;
            if (STAGE_LIST.includes(stageRef)) {
                const badgeClassName = `badge-list-ike-event__${stageRef}`;
                cellClasses += ` ${badgeClassName}`;
            }
        }
        return cellClasses;
    }
}
