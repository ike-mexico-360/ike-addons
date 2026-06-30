/** @odoo-module **/

import { Component, markup, onWillStart, onWillUnmount, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { addLoadingEffect } from '@web/core/utils/ui';
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
var new_line_id = 0;

export class PurchaseOrderDetails extends Component {
    static template = "ike_event_purchase.PurchaseOrderDetails"

    static props = {
        order_id: { type: Number, optional: false },
    };

    translate(str) { return _t(str); }

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.composerRef = useRef('composerTextarea');

        this.state = useState({
            loading: true,
            order_data: null,
            show_dispute_fields: false,
            show_approved_fields: false,
            uom_ids: [],
            product_ids: [],
            invalid_lines: new Set(),
            highlight_change_reason: false,
            xml_just_validated: false,
            composerBody: '',
            composerFiles: [],
            isSendingMessage: false,
        });

        // escuchar validación de XML
        this.__xmlValidatedHandler = async () => {
            console.log("Handler xml_validated ejecutado");
            await this._loadOrderData();
            this.state.xml_just_validated = true;
            console.log("xml_just_validated:", this.state.xml_just_validated);
            console.log("cfdi_is_valid:", this.state.order_data.cfdi_is_valid);

        };
        console.log("Disparando evento xml_validated...");
        document.addEventListener("xml_validated", this.__xmlValidatedHandler);
        console.log("Listener xml_validated registrado");
        // limpiar listener al destruir el componente
        onWillUnmount(() => {
            document.removeEventListener("xml_validated", this.__xmlValidatedHandler);
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
            const orderData = await rpc('/get_purchase_order_full_data', {
                order_id: this.props.order_id,
            });

            if (orderData) {
                this.state.order_data = orderData;
                console.log("Full Order Data with O2M:", this.state.order_data);
            }
        } catch (e) {
            this.notification.add(_t("Error loading order data: ") + e.message, {
                type: "danger",
                sticky: true
            });
        } finally {
            this.state.loading = false;
        }
    }

    formatDate(dateStr) {
        if (!dateStr) return "";
        // Converts Odoo UTC string to a local date object
        const date = deserializeDateTime(dateStr);
        // Formats to something readable, e.g., "09/05/2026 12:33:48"
        return formatDateTime(date);
    }

    formatNumber(value) {
        if (value === null || value === undefined || value === '') return '';
        const num = parseFloat(value);
        if (isNaN(num)) return value;
        return num.toFixed(2);
    }

    async _loadComplementaryData() {
        try {
            const uom_domain = await this.orm.call('product.product', 'get_concepts_uom_ids', []);
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

    // async _loadO2mTrackings(messages) {
    //     const ids = messages
    //         .filter((m) => m.o2m_tracking_command_ids?.length > 0)
    //         .map((m) => m.id);
    //     if (!ids.length) return;
    //     const o2mTrackingsMap = await this.orm.call(
    //         'mail.message',
    //         'get_o2m_tracking_format',
    //         [ids, 'purchase.order']
    //     );
    //     console.log("O2M Trackings Map:", o2mTrackingsMap);
    //     for (const msg of messages) {
    //         msg.o2mTrackings = o2mTrackingsMap[msg.id] || [];
    //     }
    // }

    messageBody(body) {
        return markup(body || '');
    }

    get isInRfqList() {
        return this.state.order_data?.state === 'sent';
    }

    get isInPurchaseOrderList() {
        return ['purchase', 'done', 'cancel'].includes(this.state.order_data.state);
    }

    get canSendMessage() {
        return (this.state.composerBody.trim().length > 0 || this.state.composerFiles.length > 0)
            && !this.state.isSendingMessage;
    }

    onComposerInput(ev) {
        this.state.composerBody = ev.target.value;
    }

    onFileSelect(ev) {
        const MAX_SIZE = 10 * 1024 * 1024;
        const files = Array.from(ev.target.files);
        const readers = files.map((file) => {
            if (file.size > MAX_SIZE) {
                this.notification.add(_t("File '%s' exceeds the 10 MB limit", file.name), { type: 'warning' });
                return null;
            }
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve({
                    name: file.name,
                    type: file.type || 'application/octet-stream',
                    size: file.size,
                    data: e.target.result.split(',')[1],
                    preview: file.type.startsWith('image/') ? e.target.result : null,
                });
                reader.readAsDataURL(file);
            });
        }).filter(Boolean);

        Promise.all(readers).then((loaded) => {
            this.state.composerFiles = [...this.state.composerFiles, ...loaded];
        });
        ev.target.value = '';
    }

    removeFile(index) {
        this.state.composerFiles = this.state.composerFiles.filter((_, i) => i !== index);
    }

    onDirectFileSelect(ev) {
        const MAX_SIZE = 10 * 1024 * 1024;
        const files = Array.from(ev.target.files);
        const readers = files.map((file) => {
            if (file.size > MAX_SIZE) {
                this.notification.add(_t("File '%s' exceeds the 10 MB limit", file.name), { type: 'warning' });
                return null;
            }
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve({
                    name: file.name,
                    type: file.type || 'application/octet-stream',
                    data: e.target.result.split(',')[1],
                });
                reader.readAsDataURL(file);
            });
        }).filter(Boolean);

        ev.target.value = '';
        Promise.all(readers).then((loaded) => this._uploadDirectFiles(loaded));
    }

    _uploadDirectFiles = async (files) => {
        if (!files.length) return;
        try {
            const result = await rpc('/my/purchase/' + this.props.order_id + '/upload_files', {
                attachments: files.map((f) => ({ name: f.name, data: f.data, mimetype: f.type })),
            });
            if (result.success) {
                this.state.order_data.order_attachment_ids = result.attachments;
            } else {
                this.notification.add(_t("Error: ") + result.error, { type: 'danger' });
            }
        } catch (e) {
            this.notification.add(_t("Error uploading files: ") + (e?.data?.message || e.message), {
                type: 'danger', sticky: true,
            });
        }
    }

    postMessage = async (ev) => {
        if (!this.canSendMessage) return;
        const disableBtn = addLoadingEffect(ev.currentTarget);
        this.state.isSendingMessage = true;
        try {
            const result = await rpc('/my/purchase/' + this.props.order_id + '/post_message', {
                body: this.state.composerBody,
                attachments: this.state.composerFiles.map((f) => ({
                    name: f.name,
                    data: f.data,
                    mimetype: f.type,
                })),
            });
            if (result.success) {
                this.state.composerBody = '';
                this.state.composerFiles = [];
                if (this.composerRef.el) this.composerRef.el.value = '';
                await this._loadOrderData();
                this.notification.add(_t("Message sent"), { type: 'success' });
            } else {
                this.notification.add(_t("Error: ") + result.error, { type: 'danger' });
            }
        } catch (e) {
            this.notification.add(_t("Error sending message: ") + (e?.data?.message || e.message), {
                type: 'danger', sticky: true
            });
        } finally {
            this.state.isSendingMessage = false;
            disableBtn();
        }
    }

    get requireChangeReason() {
        return this.state.order_data.order_line.some((l) => l.x_has_dispute_changes === true);
    }

    getProductImage(line) {
        const img = line.product_id?.image_1024;
        if (!img) return "/web/static/img/placeholder.png";
        return `data:image/png;base64,${img}`;
    }

    toggle_dispute_fields() {
        // Establecer valores por defecto
        if (this.state.show_dispute_fields == false) {
            this.state.order_data.order_line = this.state.order_data.order_line.map((line) => {
                const new_price = line.x_price_unit_dispute || line.price_unit;
                const new_qty = line.x_product_qty_dispute || line.product_qty;

                // Hubo cambio real si el campo dispute ya tenía un valor distinto al original
                const changed = (line.x_price_unit_dispute && line.x_price_unit_dispute !== line.price_unit)
                    || (line.x_product_qty_dispute && line.x_product_qty_dispute !== line.product_qty);

                return {
                    ...line,
                    x_price_unit_dispute: new_price,
                    x_product_qty_dispute: new_qty,
                    // ...(changed && { x_has_dispute_changes: true }),  // Para que se guarde el cambio en la base de datos
                };
            });
            // Calculate initial dispute total when showing dispute fields
            this._calculateAmountUntaxedDispute();
        }
        this.state.show_dispute_fields = !this.state.show_dispute_fields;
    }

    toggle_approved_fields() {
        this.state.show_approved_fields = !this.state.show_approved_fields;
    }

    accept_prices = async (ev) => {
        const disableAcceptBtn = addLoadingEffect(ev.currentTarget);
        try {
            await this.orm.call('purchase.order', 'x_portal_action_accept_prices', [this.props.order_id]);
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
            x_has_dispute_changes: true,
        });
        // Recalculate dispute total after adding new line
        this._calculateAmountUntaxedDispute();
    }

    // Eliminar la linea del state.order_data.order_line
    remove_line = async (lineId) => {
        this.state.order_data.order_line = this.state.order_data.order_line.filter(
            (l) => l.id !== lineId
        );
        // Recalculate dispute total after removing line
        this._calculateAmountUntaxedDispute();
    }

    // Validar campos de línea sin valor
    _validate_field = (lineId, fieldName, value) => {
        const line = this.state.order_data.order_line.find((l) => l.id === lineId);
        if (line?.display_type === 'line_section') {
            return true;
        }

        const fieldsAllowZero = ['price_unit', 'x_price_unit_dispute'];
        const key = `${lineId}_${fieldName}`;

        const allowZero = fieldsAllowZero.includes(fieldName);

        const isInvalid = allowZero
            ? (value == null || value < 0)
            : (value == null || value <= 0);

        if (isInvalid) {
            this.state.invalid_lines.add(key);
            return false;
        }

        this.state.invalid_lines.delete(key);
        return true;
    }

    // Calculate amount_untaxed_dispute based on dispute values
    _calculateAmountUntaxedDispute = () => {
        let total = 0;
        for (const line of this.state.order_data.order_line) {
            const price = line.x_price_unit_dispute || 0;
            const qty = line.x_product_qty_dispute || 0;
            total += price * qty;
        }
        this.state.order_data.amount_untaxed_dispute = total;
    }

    onchange_reasons = async (fieldName, value) => {
        this.state.order_data.x_change_comments = value;
    }

    // Al cambiar el valor de un campo de línea, actualizar el state.order_data.order_line
    onchange_disputed_value = async (lineId, fieldName, value) => {
        let extra = {};
        const line = this.state.order_data.order_line.find((l) => l.id === lineId);
        // Establecer UoM configurado en el concepto (solo para líneas nuevas)
        if (line?.new_line && fieldName === 'product_id' && value) {
            const product = this.state.product_ids.find((p) => p.id === value);
            const event_id = this.state.order_data.x_event_public_id.id;
            const supplier_id = this.state.order_data.partner_id.id;
            const matrix_lines = await rpc('/my/purchase/' + product.id + '/get_matrix_lines', {
                event_id: event_id,
                supplier_id: supplier_id,
            });
            let price_unit = 0;
            let has_matrix_cost = false;
            if (matrix_lines.success === true && matrix_lines.matrix_lines.length > 0) {
                console.log("matrix_lines", matrix_lines.matrix_lines);
                price_unit = matrix_lines.matrix_lines[0].cost;
                has_matrix_cost = true;
            }
            if (product?.uom_id) {
                extra = { price_unit: price_unit, has_matrix_cost: has_matrix_cost, product_uom: product.uom_id.id, product_uom_name: product.uom_id.display_name };
            }
        }

        this.state.order_data.order_line = this.state.order_data.order_line.map((l) =>
            l.id === lineId
                ? { ...l, [fieldName]: value, ...extra, x_has_dispute_changes: true }
                : l
        );
        this._validate_field(lineId, fieldName, value);

        // Recalculate amount_untaxed_dispute when dispute fields change
        if (fieldName === 'x_price_unit_dispute' || fieldName === 'x_product_qty_dispute') {
            this._calculateAmountUntaxedDispute();
        }
    }

    // Funcionalidad del botón enviar disputa
    send_dispute = async (ev) => {
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

        const disableBtn = addLoadingEffect(ev.currentTarget);
        if (this.state.invalid_lines.size > 0) {
            this.notification.add(_t("There are fields with invalid values"), {
                type: "danger"
            });
            disableBtn();
            return;
        }
        if (!(this.state.order_data.x_change_comments || '').trim()) {
            this.notification.add(_t("You must specify a reason for the change"), {
                type: "warning"
            });
            this.state.highlight_change_reason = true;
            disableBtn();
            return;
        }
        this.state.highlight_change_reason = false;
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
        const iterationCount = this.state.order_data.x_dispute_iteration_count;

        for (const line of order_line) {
            const vals = {
                x_price_unit_dispute: line.x_price_unit_dispute,
                x_product_qty_dispute: line.x_product_qty_dispute,
                x_has_dispute_changes: line.x_has_dispute_changes || false,
            };

            // Establecer los campos aprobados igual a los campos originales, solo en la primer iteración
            if (iterationCount === 0) {
                vals.x_price_unit_approved = line.price_unit;
                vals.x_product_qty_approved = line.product_qty;
            }

            if (line.new_line) {
                commands.push([0, 0, {
                    product_id: line.product_id?.id || line.product_id,
                    product_qty: line.product_qty,
                    product_uom: line.product_uom?.id || line.product_uom,
                    price_unit: line.price_unit,
                    ...vals,
                }]);
            } else {
                commands.push([1, line.id, vals]);
            }
        }

        if (commands.length === 0) {
            this.notification.add(_t("No changes to save"), { type: "info" });
            return false;
        }

        try {
            await this.orm.write("purchase.order", [this.props.order_id], {
                // Incrementar x_dispute_iteration_count en 1
                x_dispute_iteration_count: this.state.order_data.x_dispute_iteration_count + 1,
                x_change_comments: this.state.order_data.x_change_comments,
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
    download_cfdi_pdf2 = () => {
        const invoiceId = this.state.order_data?.invoice;
        if (!invoiceId) {
            this.notification.add(_t("No validated CFDI found for this order."), { type: "warning" });
            return;
        }
        window.open(`/my/purchase/download_cfdi_pdf2/${invoiceId}`, '_blank');
    }
}

registry.category("public_components").add("ike_event_purchase.purchase_order_details", PurchaseOrderDetails);