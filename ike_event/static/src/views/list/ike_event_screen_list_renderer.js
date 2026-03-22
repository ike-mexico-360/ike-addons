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
    'close',
    'cancel',
]

export class IkeEventScreenListRenderer extends ListRenderer {
    static template = "ike_event.IkeEventScreenListRenderer";
    static components = {
        ...ListRenderer.components,
        IkeEventListButtons,
    }

    /**
     * Aplica clases CSS personalizadas a las filas de la lista de Eventos
     */
    getRowClass(record) {
        let rowClasses = super.getRowClass(record);

        const stageRef = record.data.stage_ref;
        if (STAGE_LIST.includes(stageRef)) {
            const rowClassName = `bg-list-ike-event__${stageRef}`;
            rowClasses += ` ${rowClassName}`;
        }

        return rowClasses;
    }

    /**
     * Aplica clases CSS personalizadas a los badges stage_id de la lista de Eventos, necesario el widget badge
     */
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
