/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { addLoadingEffect } from '@web/core/utils/ui';
import { registry } from "@web/core/registry";


var new_line_id = 0;

export class PurchaseOrderDetails extends Component {
    static template = "ike_event_purchase.PurchaseOrderDetails"

    static props = {
        order_id: { type: Number, optional: false },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            order_data: null,
            show_dispute_fields: false,
            show_approved_fields: false,
            uom_ids: [],
            product_ids: [],
            invalid_lines: new Set(),
        });

        // Cargar datos de la orden al iniciar el componente
        onWillStart(async () => {
            await this._loadOrderData();
            await this._loadComplementaryData();
        });
    }

    async _loadOrderData() {
        this.state.loading = true;
        try {
            const order_data = await this.orm.webSearchRead(
                'purchase.order',
                [
                    ['id', '=', this.props.order_id]
                ],
                {
                    specification: {
                        id: {},
                        name: {},
                        state: {},
                        x_dispute_state: {},
                        x_dispute_approved: {},
                        order_line: {
                            fields: {
                                id: {},
                                name: {},
                                display_name: {},
                                product_id: {
                                    fields: {
                                        id: {},
                                        name: {},
                                        image_1024: {},
                                    },
                                },
                                product_qty: {},
                                product_uom: {
                                    fields: {
                                        id: {},
                                        name: {},
                                        display_name: {},
                                    },
                                },
                                price_unit: {},
                                taxes_id: {
                                    fields: {
                                        id: {},
                                        name: {},
                                        display_name: {},
                                    },
                                },
                                x_price_unit_dispute: {},
                                x_product_qty_dispute: {},
                                x_price_unit_approved: {},
                                x_product_qty_approved: {},
                            },
                        }
                    }
                }
            );
            this.state.order_data = order_data.records[0];
        } catch (e) {
            this.notification.add(_t("Error loading order data: ") + e.message, {
                type: "danger", sticky: true
            });
        } finally {
            this.state.loading = false;
        }
    }

    async _loadComplementaryData() {
        try {
            const uom_domain = await this.orm.call('product.product', 'get_concepts_uom_ids', [this.props.order_id]);
            const concepts_domain = await this.orm.call('product.product', 'get_concepts_domain', []);
            const [uom_ids, product_ids] = await Promise.all([
                this.orm.searchRead(
                    'uom.uom',
                    [['id', 'in', uom_domain]],
                    ['id', 'name', 'display_name']
                ),
                this.orm.webSearchRead(
                    'product.product',
                    concepts_domain,
                    {
                        specification: {
                            id: {},
                            name: {},
                            display_name: {},
                            standard_price: {},
                            uom_id: {
                                fields: {
                                    id: {},
                                    name: {},
                                    display_name: {},
                                },
                            },
                        },
                    }
                )
            ]);
            this.state.uom_ids = uom_ids;
            this.state.product_ids = product_ids.records;
        } catch (e) {
            this.notification.add(_t("Error loading complementary data: ") + (e?.data?.message || e.message), {
                type: "danger", sticky: true
            });
        }
    }

    getProductImage(line) {
        const img = line.product_id?.image_1024;
        if (!img) return "/web/static/img/placeholder.png";
        return `data:image/png;base64,${img}`;
    }

    toggle_dispute_fields() {
        // Establecer valores por defecto
        if (this.state.show_dispute_fields == false) {
            this.state.order_data.order_line = this.state.order_data.order_line.map((line) => ({
                ...line,
                x_price_unit_dispute: line.x_price_unit_dispute || line.price_unit,
                x_product_qty_dispute: line.x_product_qty_dispute || line.product_qty,
                changed_line: true,  // Para que se guarde el cambio en la base de datos
            }));
        }
        this.state.show_dispute_fields = !this.state.show_dispute_fields;
    }

    toggle_approved_fields() {
        this.state.show_approved_fields = !this.state.show_approved_fields;
    }

    accept_prices = async (ev) => {
        const disableAcceptBtn = addLoadingEffect(ev.currentTarget);
        try {
            await this.orm.call('purchase.order', 'x_action_accept_prices', [this.props.order_id]);
            await this._loadOrderData();
        } catch (e) {
            this.notification.add(_t("Error at accept prices: ") + (e?.data?.message || e.message), {
                type: "danger", sticky: true
            });
        } finally {
            disableAcceptBtn();
        }
    }

    // Añadir linea virtual en state.order_data.order_line
    add_line = async () => {
        this.state.order_data.order_line.push({
            id: "virtual_" + new_line_id++,
            name: "",
            product_id: false,
            product_uom: false,
            product_qty: 1,
            price_unit: 0,
            taxes_id: [],
            x_price_unit_dispute: 0,
            x_product_qty_dispute: 0,
            x_price_unit_approved: 0,
            x_product_qty_approved: 0,
            new_line: true,
        });
    }

    // Eliminar la linea del state.order_data.order_line
    remove_line = async (lineId) => {
        this.state.order_data.order_line = this.state.order_data.order_line.filter(
            (l) => l.id !== lineId
        );
    }

    // Validar campos de línea sin valor
    _validate_field = (lineId, fieldName, value) => {
        const key = `${lineId}_${fieldName}`;
        if (value <= 0 || value == null) {
            this.state.invalid_lines.add(key);
            return false;
        }
        this.state.invalid_lines.delete(key);
        return true;
    }

    // Al cambiar el valor de un campo de línea, actualizar el state.order_data.order_line
    onchange_disputed_value = async (lineId, fieldName, value) => {
        let extra = {};

        // Establecer UoM configurado en el concepto
        if (fieldName === 'product_id') {
            const product = this.state.product_ids.find((p) => p.id === value);
            if (product?.uom_id) {
                extra = { price_unit: product.standard_price, product_uom: product.uom_id.id, product_uom_name: product.uom_id.display_name };
            }
        }

        this.state.order_data.order_line = this.state.order_data.order_line.map((l) =>
            l.id === lineId
                ? { ...l, [fieldName]: value, ...extra, changed_line: true }
                : l
        );
        this._validate_field(lineId, fieldName, value);
    }

    // Funcionalidad del botón enviar disputa
    send_dispute = async (ev) => {
        const disableBtn = addLoadingEffect(ev.currentTarget);

        this.state.invalid_lines = new Set();
        const order_line = this.state.order_data.order_line;
        const dispute_fields = ['x_price_unit_dispute', 'x_product_qty_dispute'];
        const new_line_fields = ['product_id', 'product_uom', 'product_qty', 'price_unit']

        for (const line of order_line) {
            dispute_fields.forEach((field) => this._validate_field(line.id, field, line[field]))
            if (line.new_line) {
                new_line_fields.forEach((field) => this._validate_field(line.id, field, line[field]))
            }
        }
        if (this.state.invalid_lines.size > 0) {
            this.notification.add(_t("There are fields with invalid values"), {
                type: "danger"
            });
            disableBtn();
            return;
        }
        try {
            const saved = await this._saveDispute(order_line);
            if (saved) {
                await this.orm.call('purchase.order', 'x_action_submit_dispute', [this.props.order_id]);
                await this._loadOrderData();
                await this._loadComplementaryData();
                this.toggle_dispute_fields();
                this.notification.add(_t("Dispute sent successfully"), { type: "success" });
            }
        } catch (e) {
            this.notification.add(_t("Error sending dispute: ") + (e?.data?.message || e.message), {
                type: "danger", sticky: true
            });
        } finally {
            disableBtn();
        }
    }

    // Guardar los cambios e la base de datos
    _saveDispute = async (order_line) => {
        const commands = [];

        for (const line of order_line) {
            const vals = {
                x_price_unit_dispute: line.x_price_unit_dispute,
                x_product_qty_dispute: line.x_product_qty_dispute,
            };

            if (line.new_line) {
                commands.push([0, 0, {
                    product_id: line.product_id?.id || line.product_id,
                    product_qty: line.product_qty,
                    product_uom: line.product_uom?.id || line.product_uom,
                    price_unit: line.price_unit,
                    ...vals,
                }]);
            } else if (line.changed_line) {
                commands.push([1, line.id, vals]);
            }
        }

        if (commands.length === 0) {
            this.notification.add(_t("No changes to save"), { type: "info" });
            return false;
        }

        try {
            await this.orm.write("purchase.order", [this.props.order_id], {
                order_line: commands,
            });
            return true;
        } catch (e) {
            this.notification.add(_t("Error sending dispute: ") + (e?.data?.message || e.message), {
                type: "danger", sticky: true
            });
            return false;
        }
    }
}

registry.category("public_components").add("ike_event_purchase.purchase_order_details", PurchaseOrderDetails);
