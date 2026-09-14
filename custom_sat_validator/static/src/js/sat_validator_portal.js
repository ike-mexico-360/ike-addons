/** @odoo-module */

import { _t } from "@web/core/l10n/translation";

const SatValidatorState = {
    xmlBase64: null,
    xmlFilename: '',
    pdfBase64: null,
    pdfFilename: '',
    cpBase64: null,
    cpFilename: '',
    draggedElement: null,
    isOneToNCase: false,

    /**
     * Converts a File object to a Base64-encoded string.
     */
    _fileToBase64: function (file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result.split(',')[1]);
            reader.onerror = error => reject(error);
        });
    },

    /**
     * Clears and hides top process alerts and modal validation feedback messages.
     */
    clearNotifications: function () {
        const topFeedback = document.getElementById('sat_process_xml_alert');
        const bottomFeedback = document.getElementById('sat_modal_validation_feedback');

        if (topFeedback) {
            topFeedback.classList.add('d-none');
            topFeedback.classList.remove('alert-danger', 'alert-success', 'alert-warning');
            topFeedback.innerHTML = '';
        }
        if (bottomFeedback) {
            bottomFeedback.style.display = 'none';
            bottomFeedback.innerHTML = '';
        }
    },

    /**
     * Displays a notification alert in the main top container or falls back to browser alert.
     */
    _showProcessNotification: function (message, type = 'danger', title = '') {
        const feedbackElem = document.getElementById('sat_process_xml_alert');
        if (feedbackElem) {
            feedbackElem.classList.remove('d-none', 'alert-danger', 'alert-success', 'alert-warning');
            feedbackElem.classList.add(`alert-${type}`);
            feedbackElem.innerHTML = `<strong>${title ? title + ': ' : ''}</strong>${message}`;
        } else {
            alert(`${title ? title + ': ' : ''}${message}`);
        }
    },

    /**
     * Displays a notification inside the modal feedback container or falls back to browser alert.
     */
    _showInvoiceNotification: function (message, type = 'danger', title = '') {
        const feedbackElem = document.getElementById('sat_modal_validation_feedback');
        if (feedbackElem) {
            feedbackElem.style.display = 'block';
            feedbackElem.innerHTML = `<div class="alert alert-${type} py-1 mb-0 small"><strong>${title ? title + ': ' : ''}</strong>${message}</div>`;
        } else {
            alert(`${title ? title + ': ' : ''}${message}`);
        }
    },

    /**
     * Applies dynamic custom styles to line checkboxes based on their checked state.
     */
    _applyCheckboxStyles: function (checkbox) {
        if (!checkbox) return;
        if (checkbox.checked) {
            checkbox.style.setProperty('background-color', '#2F6FB0', 'important');
            checkbox.style.setProperty('border-color', '#2F6FB0', 'important');
        } else {
            checkbox.style.setProperty('background-color', '#ffffff', 'important');
            checkbox.style.setProperty('border-color', '#B0C4DE', 'important');
        }
        checkbox.style.setProperty('accent-color', '#2F6FB0', 'important');
    },

    /**
     * Synchronizes purchase order line checkboxes based on matching XML items in slots or one-to-N logic.
     */
    syncCheckboxesWithSlots: function () {
        const poRows = document.querySelectorAll('#local_sat_po_tbody tr:not(#empty_po_row)');

        if (this.isOneToNCase) {
            poRows.forEach((poRow) => {
                const checkbox = poRow.querySelector('.sat-line-checkbox');
                if (checkbox) {
                    checkbox.checked = true;
                    this._applyCheckboxStyles(checkbox);
                }
            });
        } else {
            poRows.forEach((poRow, idx) => {
                const checkbox = poRow.querySelector('.sat-line-checkbox');
                const slotTd = document.querySelector(`.xml-drop-slot[data-slot-index="${idx}"]`);

                if (checkbox && slotTd) {
                    const hasXmlItem = slotTd.querySelector('.xml-drag-item') !== null || slotTd.classList.contains('xml-drag-item');
                    checkbox.checked = hasXmlItem;
                    this._applyCheckboxStyles(checkbox);
                }
            });
        }
    },

    /**
     * Equalizes row heights across PO lines and XML lines tables to ensure visual alignment.
     */
    syncRowHeights: function () {
        requestAnimationFrame(() => {
            const poRows = document.querySelectorAll('#local_sat_po_tbody tr:not(#empty_po_row)');
            const xmlRows = document.querySelectorAll('#local_sat_xml_tbody tr:not(#empty_xml_row)');

            poRows.forEach((poRow, idx) => {
                const xmlRow = xmlRows[idx];
                if (xmlRow) {
                    poRow.style.height = 'auto';
                    xmlRow.style.height = 'auto';

                    const maxHeight = Math.max(poRow.getBoundingClientRect().height, xmlRow.getBoundingClientRect().height);
                    const heightPx = `${Math.ceil(maxHeight)}px`;

                    poRow.style.height = heightPx;
                    xmlRow.style.height = heightPx;
                }
            });
        });
    },

    /**
     * Calculates total subtotals for PO and XML lines, updates summary UI, and enables/disables the validation button.
     */
    updateTableTotals: function () {
        let totalPo = 0.0;
        let totalXml = 0.0;

        const poRows = document.querySelectorAll('#local_sat_po_tbody tr:not(#empty_po_row)');
        poRows.forEach(row => {
            const checkbox = row.querySelector('.sat-line-checkbox');
            const poSubtotalAttr = row.getAttribute('data-po-subtotal');

            if (checkbox) {
                this._applyCheckboxStyles(checkbox);
            }

            if (checkbox && checkbox.checked && poSubtotalAttr) {
                totalPo += parseFloat(poSubtotalAttr) || 0.0;
            }
        });

        const xmlItems = document.querySelectorAll('.xml-drag-item');
        xmlItems.forEach(item => {
            const xmlSubtotalAttr = item.getAttribute('data-xml-subtotal');
            if (xmlSubtotalAttr) {
                totalXml += parseFloat(xmlSubtotalAttr) || 0.0;
            }
        });

        const poTotalElem = document.getElementById('po_total_subtotal');
        const xmlTotalElem = document.getElementById('xml_total_subtotal');
        const tfootElem = document.getElementById('local_sat_package_preview_tfoot');
        const validateBtn = document.getElementById('validate_all_sat_packages_btn');

        if (poTotalElem) poTotalElem.innerText = `$${totalPo.toFixed(2)}`;
        if (xmlTotalElem) xmlTotalElem.innerText = `$${totalXml.toFixed(2)}`;

        const isMatching = totalPo > 0 && Math.abs(totalPo - totalXml) < 0.01;

        if (poTotalElem && xmlTotalElem) {
            if (isMatching) {
                poTotalElem.className = 'fw-bold text-success';
                xmlTotalElem.className = 'fw-bold text-success';
            } else {
                poTotalElem.className = 'fw-bold text-dark';
                xmlTotalElem.className = 'fw-bold text-dark';
            }
        }

        if (validateBtn) {
            if (isMatching) {
                validateBtn.removeAttribute('disabled');
            } else {
                validateBtn.setAttribute('disabled', 'disabled');
            }
        }

        if (tfootElem) tfootElem.style.display = poRows.length > 0 ? 'block' : 'none';
    },

    /**
     * Resets the modal state, clears inputs, restores default placeholder rows, and hides footer elements.
     */
    resetModal: function () {
        this.xmlBase64 = null;
        this.xmlFilename = '';
        this.pdfBase64 = null;
        this.pdfFilename = '';
        this.cpBase64 = null;
        this.cpFilename = '';
        this.draggedElement = null;
        this.isOneToNCase = false;

        const xmlInput = document.getElementById('portal_sat_xml_file');
        const pdfInput = document.getElementById('portal_sat_pdf_file');
        const cpInput = document.getElementById('portal_sat_cp_file');

        if (xmlInput) xmlInput.value = '';
        if (pdfInput) pdfInput.value = '';
        if (cpInput) cpInput.value = '';

        const poTbody = document.getElementById('local_sat_po_tbody');
        if (poTbody) {
            poTbody.innerHTML = `
                <tr id="empty_po_row">
                    <td colspan="5" class="text-center text-muted py-3 small">
                        <i class="fa fa-info-circle me-1"/> Upload and process a CFDI XML file to load purchase lines.
                    </td>
                </tr>
            `;
        }

        const xmlTbody = document.getElementById('local_sat_xml_tbody');
        if (xmlTbody) {
            xmlTbody.innerHTML = `
                <tr id="empty_xml_row">
                    <td colspan="3" class="text-center text-muted py-3 small">
                        <i class="fa fa-info-circle me-1"/> Process XML to view CFDI lines.
                    </td>
                </tr>
            `;
        }

        const tfootElem = document.getElementById('local_sat_package_preview_tfoot');
        if (tfootElem) tfootElem.style.display = 'none';

        const validateBtn = document.getElementById('validate_all_sat_packages_btn');
        if (validateBtn) validateBtn.setAttribute('disabled', 'disabled');

        this.clearNotifications();
    },

    /**
     * Initializes drag-and-drop event handlers on XML table rows for reordering and amount validation.
     */
    _setupDragAndDrop: function () {
        if (this.isOneToNCase) return;

        const self = this;
        const tbody = document.getElementById('local_sat_xml_tbody');
        if (!tbody) return;

        tbody.addEventListener('dragstart', function (e) {
            const row = e.target.closest('tr.xml-drag-item');
            if (row) {
                self.draggedElement = row;
                e.dataTransfer.setData('text/plain', '');
                row.classList.add('dragging');
            }
        });

        tbody.addEventListener('dragend', function (e) {
            const row = e.target.closest('tr.xml-drag-item');
            if (row) {
                row.classList.remove('dragging');
            }
            self.draggedElement = null;
        });

        tbody.addEventListener('dragover', function (e) {
            e.preventDefault();
            const slotRow = e.target.closest('tr.xml-drop-slot');
            if (slotRow && self.draggedElement && slotRow !== self.draggedElement) {
                slotRow.classList.add('drag-over');
            }
        });

        tbody.addEventListener('dragleave', function (e) {
            const slotRow = e.target.closest('tr.xml-drop-slot');
            if (slotRow) {
                slotRow.classList.remove('drag-over');
            }
        });

        tbody.addEventListener('drop', function (e) {
            e.preventDefault();
            const targetRow = e.target.closest('tr.xml-drop-slot');

            if (targetRow && self.draggedElement && targetRow !== self.draggedElement) {
                targetRow.classList.remove('drag-over');

                // AMOUNT VALIDATION: Map with the opposite PO line using data-slot-index
                const slotIndex = parseInt(targetRow.getAttribute('data-slot-index'), 10);
                const poRows = document.querySelectorAll('#local_sat_po_tbody tr:not(#empty_po_row)');
                const targetPoRow = poRows[slotIndex];

                if (targetPoRow) {
                    const poSubtotal = parseFloat(targetPoRow.getAttribute('data-po-subtotal')) || 0.0;
                    const draggedXmlSubtotal = parseFloat(self.draggedElement.getAttribute('data-xml-subtotal')) || 0.0;

                    // Cancel drag-and-drop if amounts differ and display alert notification
                    if (Math.abs(poSubtotal - draggedXmlSubtotal) >= 0.01) {
                        self._showInvoiceNotification(
                            _t(`Cannot move line. XML line amount ($${draggedXmlSubtotal.toFixed(2)}) does not match PO line amount ($${poSubtotal.toFixed(2)}).`),
                            'warning',
                            _t('Invalid Alignment')
                        );
                        return;
                    }
                }

                // Clear previous notification and swap cell attributes if amounts match
                self.clearNotifications();

                const sourceHtml = self.draggedElement.innerHTML;
                const sourceSubtotal = self.draggedElement.getAttribute('data-xml-subtotal');
                const sourceDraggable = self.draggedElement.getAttribute('draggable');
                const sourceIsDragItem = self.draggedElement.classList.contains('xml-drag-item');

                const targetHtml = targetRow.innerHTML;
                const targetSubtotal = targetRow.getAttribute('data-xml-subtotal');
                const targetDraggable = targetRow.getAttribute('draggable');
                const targetIsDragItem = targetRow.classList.contains('xml-drag-item');

                self.draggedElement.innerHTML = targetHtml;
                if (targetSubtotal !== null) {
                    self.draggedElement.setAttribute('data-xml-subtotal', targetSubtotal);
                } else {
                    self.draggedElement.removeAttribute('data-xml-subtotal');
                }
                if (targetDraggable) {
                    self.draggedElement.setAttribute('draggable', targetDraggable);
                } else {
                    self.draggedElement.removeAttribute('draggable');
                }
                if (targetIsDragItem) {
                    self.draggedElement.classList.add('xml-drag-item');
                } else {
                    self.draggedElement.classList.remove('xml-drag-item');
                }

                targetRow.innerHTML = sourceHtml;
                if (sourceSubtotal !== null) {
                    targetRow.setAttribute('data-xml-subtotal', sourceSubtotal);
                } else {
                    targetRow.removeAttribute('data-xml-subtotal');
                }
                if (sourceDraggable) {
                    targetRow.setAttribute('draggable', sourceDraggable);
                } else {
                    targetRow.removeAttribute('draggable');
                }
                if (sourceIsDragItem) {
                    targetRow.classList.add('xml-drag-item');
                } else {
                    targetRow.classList.remove('xml-drag-item');
                }

                self.syncCheckboxesWithSlots();
                self.updateTableTotals();
                self.syncRowHeights();
            }
        });
    }
};

// Global Event Delegation Listener
/**
 * Global click event listener handling XML processing and invoice validation actions.
 */
document.addEventListener('click', async function (ev) {

    const btnProcess = ev.target.closest('#process_sat_xml_btn');
    if (btnProcess) {
        ev.preventDefault();
        SatValidatorState.clearNotifications();

        const xmlInput = document.getElementById('portal_sat_xml_file');
        const pdfInput = document.getElementById('portal_sat_pdf_file');
        const cpInput = document.getElementById('portal_sat_cp_file');

        const rawOrderId = btnProcess.getAttribute('data-order-id');
        const purchaseOrderId = parseInt(rawOrderId, 10);

        if (isNaN(purchaseOrderId) || purchaseOrderId <= 0) {
            SatValidatorState._showProcessNotification(_t("Invalid Purchase Order ID reference."), 'danger', _t('Missing Reference'));
            return;
        }

        if (!xmlInput || !xmlInput.files || xmlInput.files.length === 0) {
            SatValidatorState._showProcessNotification(_t("The CFDI XML file is required."), 'danger', _t('Missing Document'));
            return;
        }
        if (!pdfInput || !pdfInput.files || pdfInput.files.length === 0) {
            SatValidatorState._showProcessNotification(_t("The Vendor Bill PDF file is strictly required."), 'danger', _t('Missing Document'));
            return;
        }

        const xmlFile = xmlInput.files[0];
        const pdfFile = pdfInput && pdfInput.files.length > 0 ? pdfInput.files[0] : null;
        const cpFile = cpInput && cpInput.files.length > 0 ? cpInput.files[0] : null;

        btnProcess.setAttribute('disabled', 'disabled');
        btnProcess.innerHTML = `<i class="fa fa-spinner fa-spin me-1"/> ${_t("Processing...")}`;

        try {
            SatValidatorState.xmlBase64 = await SatValidatorState._fileToBase64(xmlFile);
            SatValidatorState.xmlFilename = xmlFile.name;
            SatValidatorState.pdfBase64 = pdfFile ? await SatValidatorState._fileToBase64(pdfFile) : false;
            SatValidatorState.pdfFilename = pdfFile ? pdfFile.name : '';
            SatValidatorState.cpBase64 = cpFile ? await SatValidatorState._fileToBase64(cpFile) : false;
            SatValidatorState.cpFilename = cpFile ? cpFile.name : '';

            const csrfToken = (window.odoo && window.odoo.csrf_token) ? window.odoo.csrf_token : '';

            const response = await fetch("/my/purchase/preview_sat_xml_lines", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        purchase_order_id: purchaseOrderId,
                        xml_file: SatValidatorState.xmlBase64,
                        filename: SatValidatorState.xmlFilename
                    },
                    id: Math.floor(Math.random() * 1000)
                })
            });

            const data = await response.json();

            btnProcess.removeAttribute('disabled');
            btnProcess.innerHTML = `<i class="fa fa-cogs me-1"/> ${_t("Process XML")}`;

            if (data.error) {
                throw new Error(data.error.data?.message || data.error.message || _t("Server error processing XML."));
            }

            const result = data.result;
            if (result && result.success) {
                const poTbody = document.getElementById('local_sat_po_tbody');
                const xmlTbody = document.getElementById('local_sat_xml_tbody');

                poTbody.innerHTML = '';
                xmlTbody.innerHTML = '';

                const rawLines = result.lines || [];

                const poLinesData = rawLines.map(l => ({
                    po_line_id: l.po_line_id,
                    po_product_name: l.po_product_name,
                    x_parent_expedient: l.x_parent_expedient,
                    po_qty: l.po_qty,
                    po_subtotal: l.po_subtotal !== undefined && l.po_subtotal !== null ? parseFloat(l.po_subtotal) : 0.0
                }));

                const xmlLinesData = rawLines
                    .filter(l => (l.xml_subtotal !== undefined && l.xml_subtotal !== null && parseFloat(l.xml_subtotal) > 0) || l.xml_product_name)
                    .map(l => ({
                        xml_folio: l.xml_folio || '',
                        xml_product_name: l.xml_product_name || '',
                        xml_subtotal: l.xml_subtotal !== undefined && l.xml_subtotal !== null ? parseFloat(l.xml_subtotal) : 0.0
                    }));

                const totalPoSum = poLinesData.reduce((acc, curr) => acc + curr.po_subtotal, 0.0);
                const totalXmlSum = xmlLinesData.reduce((acc, curr) => acc + curr.xml_subtotal, 0.0);

                SatValidatorState.isOneToNCase = (xmlLinesData.length === 1 && poLinesData.length > 1 && Math.abs(totalPoSum - totalXmlSum) < 0.01);

                poLinesData.forEach((po) => {
                    const poTr = document.createElement('tr');
                    poTr.className = 'align-middle';
                    poTr.setAttribute('data-po-subtotal', po.po_subtotal);

                    poTr.innerHTML = `
                        <td class="fw-bold small text-truncate" style="max-width: 150px;" title="${po.po_product_name || ''}">${po.po_product_name || ''}</td>
                        <td class="small text-muted text-truncate" style="max-width: 100px;" title="${po.x_parent_expedient || ''}">${po.x_parent_expedient || ''}</td>
                        <td class="text-end small">${po.po_qty !== undefined ? po.po_qty : ''}</td>
                        <td class="text-end fw-bold small pe-2">$${po.po_subtotal.toFixed(2)}</td>
                        <td class="text-center">
                            <input type="checkbox" class="form-check-input sat-line-checkbox" value="${po.po_line_id}" disabled="disabled" style="pointer-events: none; opacity: 0.95;"/>
                        </td>
                    `;
                    poTbody.appendChild(poTr);
                });

                const slotsArray = new Array(poLinesData.length).fill(null);

                if (SatValidatorState.isOneToNCase) {
                    slotsArray[0] = xmlLinesData[0];
                } else {
                    const availableXml = [...xmlLinesData];

                    poLinesData.forEach((po, poIdx) => {
                        const matchIdx = availableXml.findIndex(x => Math.abs(x.xml_subtotal - po.po_subtotal) < 0.01);
                        if (matchIdx !== -1) {
                            slotsArray[poIdx] = availableXml[matchIdx];
                            availableXml.splice(matchIdx, 1);
                        }
                    });

                    availableXml.forEach(unmatchedXml => {
                        const emptySlotIdx = slotsArray.findIndex(slot => slot === null);
                        if (emptySlotIdx !== -1) {
                            slotsArray[emptySlotIdx] = unmatchedXml;
                        }
                    });
                }

                slotsArray.forEach((xmlItem, slotIdx) => {
                    const xmlTr = document.createElement('tr');
                    xmlTr.className = 'align-middle xml-drop-slot';
                    xmlTr.setAttribute('data-slot-index', slotIdx);

                    if (xmlItem) {
                        if (!SatValidatorState.isOneToNCase) {
                            xmlTr.setAttribute('draggable', 'true');
                        }
                        xmlTr.classList.add('xml-drag-item');
                        xmlTr.setAttribute('data-xml-subtotal', xmlItem.xml_subtotal);

                        const dragHandleHtml = !SatValidatorState.isOneToNCase ? `<i class="fa fa-bars text-secondary me-1 cursor-grab" style="font-size: 0.7rem;"/>` : '';

                        xmlTr.innerHTML = `
                            <td class="small text-muted font-monospace text-truncate px-2" style="width: 20%; max-width: 80px;" title="${xmlItem.xml_folio || ''}">
                                ${dragHandleHtml}
                                ${xmlItem.xml_folio || ''}
                            </td>
                            <td class="small fw-bold text-dark text-truncate px-2" style="width: 55%; max-width: 180px;" title="${xmlItem.xml_product_name || ''}">
                                ${xmlItem.xml_product_name || ''}
                            </td>
                            <td class="text-end small fw-bold text-primary pe-2" style="width: 25%;">
                                $${xmlItem.xml_subtotal.toFixed(2)}
                            </td>
                        `;
                    } else {
                        xmlTr.innerHTML = `
                            <td colspan="3" class="text-center text-muted small" style="background-color: #fcfcfc;">
                                <span class="fst-italic" style="font-size: 0.75rem;">--- Vacío ---</span>
                            </td>
                        `;
                    }

                    xmlTbody.appendChild(xmlTr);
                });

                SatValidatorState._setupDragAndDrop();
                SatValidatorState.syncCheckboxesWithSlots();
                SatValidatorState.updateTableTotals();
                SatValidatorState.syncRowHeights();

            } else {
                throw new Error((result && result.error) || _t("Parsing XML lines failed."));
            }

        } catch (err) {
            btnProcess.removeAttribute('disabled');
            btnProcess.innerHTML = `<i class="fa fa-cogs me-1"/> ${_t("Process XML")}`;
            SatValidatorState._showProcessNotification(err.message || err, 'danger', _t('Processing Error'));
        }
    }

    const btnValidate = ev.target.closest('#validate_all_sat_packages_btn');
    if (btnValidate) {
        ev.preventDefault();
        SatValidatorState.clearNotifications();

        const rawOrderId = btnValidate.getAttribute('data-order-id');
        const purchaseOrderId = parseInt(rawOrderId, 10);

        const selectedCheckboxes = document.querySelectorAll('.sat-line-checkbox:checked');
        const selectedPoLineIds = Array.from(selectedCheckboxes).map(cb => parseInt(cb.value, 10));

        if (selectedPoLineIds.length === 0) {
            SatValidatorState._showInvoiceNotification(_t("Please select at least one line to process."), 'warning', _t('Selection Required'));
            return;
        }

        btnValidate.setAttribute('disabled', 'disabled');
        btnValidate.innerHTML = `<i class="fa fa-spinner fa-spin me-1"/> ${_t("Processing Invoice...")}`;

        try {
            const csrfToken = (window.odoo && window.odoo.csrf_token) ? window.odoo.csrf_token : '';

            const response = await fetch("/my/purchase/process_selected_sat_lines", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken
                },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    method: "call",
                    params: {
                        purchase_order_id: purchaseOrderId,
                        selected_po_line_ids: selectedPoLineIds,
                        xml_file: SatValidatorState.xmlBase64,
                        xml_filename: SatValidatorState.xmlFilename,
                        pdf_file: SatValidatorState.pdfBase64,
                        pdf_filename: SatValidatorState.pdfFilename,
                        carta_porte_file: SatValidatorState.cpBase64
                    },
                    id: Math.floor(Math.random() * 1000)
                })
            });

            const data = await response.json();

            if (data.error) {
                throw new Error(data.error.data?.message || data.error.message || _t("Server error during invoice creation."));
            }

            const result = data.result;
            if (result && result.success) {
                SatValidatorState._showInvoiceNotification(_t("Document successfully imported and verified."), 'success', _t('Success'));

                setTimeout(() => {
                    SatValidatorState.resetModal();
                    const modalElem = document.getElementById('modal_upload_sat_packages');
                    if (modalElem && window.bootstrap) {
                        const modalInstance = window.bootstrap.Modal.getInstance(modalElem);
                        if (modalInstance) modalInstance.hide();
                    }
                    window.location.reload();
                }, 1500);

            } else {
                throw new Error((result && result.error) || _t("Validation failed."));
            }

        } catch (error) {
            btnValidate.removeAttribute('disabled');
            btnValidate.innerHTML = `<i class="fa fa-check-circle me-1"/> ${_t("Validate & Create Invoice")}`;
            SatValidatorState._showInvoiceNotification(error.message || error, 'danger', _t('Validation Error'));
        }
    }
});

/**
 * Window resize event handler to recalculate and sync row heights on screen changes.
 */
window.addEventListener('resize', () => {
    SatValidatorState.syncRowHeights();
});

/**
 * Bootstrap modal hide event listener to clear focus and reset notifications upon closing.
 */
document.addEventListener('hide.bs.modal', function (ev) {
    const targetId = ev.target ? ev.target.id : '';
    if ((targetId === 'modal_upload_sat_packages' || targetId === 'modal_history_sat_packages') &&
        document.activeElement && ev.target.contains(document.activeElement)) {
        document.activeElement.blur();
        SatValidatorState.clearNotifications();
    }
});