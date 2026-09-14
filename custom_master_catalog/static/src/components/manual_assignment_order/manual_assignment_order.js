/** @odoo-module **/

import { _t } from '@web/core/l10n/translation';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';
import { useSortable } from '@web/core/utils/sortable_owl';
import { standardActionServiceProps } from '@web/webclient/actions/action_service';
import { Component, onWillStart, useRef, useState } from '@odoo/owl';


export class ManualAssignmentOrder extends Component {
    static template = 'custom_master_catalog.ManualAssignmentOrder';
    static props = {...standardActionServiceProps};

    setup() {
        this.orm = useService('orm');
        this.notification = useService('notification');
        this.rowsRef = useRef('rows');
        this.state = useState({
            states: [],
            zones: [],
            products: [],
            stateId: 0,
            municipalityId: 0,
            productId: 0,
            rows: [],
            loading: false,
            loaded: false,
            dirty: false,
        });

        onWillStart(async () => {
            const options = await this.orm.call(
                'custom.manual.assignment.order',
                'get_manual_assignment_options',
                [],
            );
            this.state.states = options.states;
            this.state.products = options.products;
        });

        useSortable({
            ref: this.rowsRef,
            elements: '.o_manual_assignment_order_row',
            handle: '.o_manual_assignment_drag_handle',
            cursor: 'grabbing',
            placeholderClasses: [
                'd-table-row',
                'o_manual_assignment_drop_placeholder',
            ],
            followingElementClasses: ['o_manual_assignment_dragging'],
            onElementEnter: ({element}) => {
                this._clearDragTarget();
                element.classList.add('o_manual_assignment_drop_target');
            },
            onElementLeave: ({element}) => {
                element.classList.remove('o_manual_assignment_drop_target');
            },
            onDragEnd: () => this._clearDragTarget(),
            onDrop: ({element, previous, next}) => {
                const centerId = Number(element.dataset.centerId);
                const rows = this.state.rows.filter(
                    (row) => row.supplier_center_id !== centerId
                );
                let position = 0;
                if (previous) {
                    const previousId = Number(previous.dataset.centerId);
                    position = rows.findIndex(
                        (row) => row.supplier_center_id === previousId
                    ) + 1;
                } else if (!next) {
                    position = rows.length;
                }
                const movedRow = this.state.rows.find(
                    (row) => row.supplier_center_id === centerId
                );
                rows.splice(position, 0, movedRow);
                this._setRows(rows);
                this.state.dirty = true;
            },
        });
    }

    get canApply() {
        return Boolean(
            this.state.stateId
            && this.state.municipalityId
            && this.state.productId
            && !this.state.loading
        );
    }

    async onStateChange(event) {
        this.state.stateId = Number(event.target.value);
        this.state.municipalityId = 0;
        this.state.zones = [];
        this._resetResults();
        if (this.state.stateId) {
            this.state.zones = await this.orm.call(
                'custom.manual.assignment.order',
                'get_manual_assignment_zones',
                [this.state.stateId],
            );
        }
    }

    onMunicipalityChange(event) {
        this.state.municipalityId = Number(event.target.value);
        this._resetResults();
    }

    onProductChange(event) {
        this.state.productId = Number(event.target.value);
        this._resetResults();
    }

    async applyFilters() {
        if (!this.canApply) {
            return;
        }
        this.state.loading = true;
        try {
            const rows = await this.orm.call(
                'custom.manual.assignment.order',
                'get_manual_assignment_candidates',
                [
                    this.state.stateId,
                    this.state.municipalityId,
                    this.state.productId,
                ],
            );
            this._setRows(rows);
            this.state.loaded = true;
            this.state.dirty = false;
        } finally {
            this.state.loading = false;
        }
    }

    clearFilters() {
        this.state.stateId = 0;
        this.state.municipalityId = 0;
        this.state.productId = 0;
        this.state.zones = [];
        this._resetResults();
    }

    removeRow(centerId) {
        this._setRows(
            this.state.rows.filter((row) => row.supplier_center_id !== centerId)
        );
        this.state.dirty = true;
    }

    setPriority(centerId, priority) {
        const row = this.state.rows.find(
            (item) => item.supplier_center_id === centerId
        );
        if (!row) {
            return;
        }
        row.priority = row.priority === priority ? 0 : priority;
        this.state.dirty = true;
    }

    async save() {
        this.state.loading = true;
        try {
            await this.orm.call(
                'custom.manual.assignment.order',
                'save_manual_assignment_order',
                [
                    this.state.stateId,
                    this.state.municipalityId,
                    this.state.productId,
                    this.state.rows.map((row) => ({
                        supplier_center_id: row.supplier_center_id,
                        priority: row.priority,
                    })),
                ],
            );
            this.state.dirty = false;
            this.notification.add(_t('Manual assignment order saved.'), {
                type: 'success',
            });
        } finally {
            this.state.loading = false;
        }
    }

    async discard() {
        await this.applyFilters();
    }

    _setRows(rows) {
        this.state.rows = rows.map((row, index) => ({
            ...row,
            sequence: index + 1,
        }));
    }

    _resetResults() {
        this.state.rows = [];
        this.state.loaded = false;
        this.state.dirty = false;
    }

    _clearDragTarget() {
        this.rowsRef.el?.querySelectorAll('.o_manual_assignment_drop_target').forEach(
            (element) => element.classList.remove('o_manual_assignment_drop_target')
        );
    }
}

registry.category('actions').add(
    'custom_master_catalog.manual_assignment_order',
    ManualAssignmentOrder,
);
