/** @odoo-module */

// Import Odoo base services if required in the Assets ecosystem
import { _t } from "@web/core/l10n/translation";

console.log("[DEBUG SAT] -> 0. The sat_validator_portal.js file has been READ by the browser.");

// Global in-memory container for the package queue
const SatValidatorQueue = {
    packages: [],

    _fileToBase64: function (file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.readAsDataURL(file);
            reader.onload = () => resolve(reader.result.split(',')[1]);
            reader.onerror = error => reject(error);
        });
    }
};

// Target modal IDs for this module to narrow down the impact of accessibility events
const myModalIds = ['modal_upload_sat_packages', 'modal_history_sat_packages'];

document.addEventListener('hide.bs.modal', function (ev) {
    // If the modal being closed is NOT one of ours, ignore the event
    if (!myModalIds.includes(ev.target.id)) return;

    if (document.activeElement && ev.target.contains(document.activeElement)) {
        document.activeElement.blur(); // Remove focus from the internal button (like the close 'X')
    }
});

document.addEventListener('hidden.bs.modal', function (ev) {
    // If the modal that was closed is NOT one of ours, ignore the event
    if (!myModalIds.includes(ev.target.id)) return;

    // Return focus to the original portal button to comply with ARIA accessibility standards
    const triggerButton = document.querySelector(`[data-bs-target="#${ev.target.id}"]`);
    if (triggerButton) {
        triggerButton.focus();
    }
});

// Native event delegation at 'document' level (Immune to Odoo/OWL re-renders)
document.addEventListener('click', async function (ev) {

    // -------------------------------------------------------------------------
    // CASE 1: CLICK ON THE "ADD PACKAGE" BUTTON (#add_package_to_list_btn)
    // -------------------------------------------------------------------------
    if (ev.target && ev.target.matches('#add_package_to_list_btn')) {
        ev.preventDefault();
        console.log("[DEBUG SAT] -> 4. CLICK DETECTED natively on #add_package_to_list_btn!");

        const xmlInput = document.getElementById('portal_xml_file');
        const pdfInput = document.getElementById('portal_pdf_file');
        const cpInput = document.getElementById('portal_cp_file');

        console.log("[DEBUG SAT] -> 5. Inputs status:", xmlInput ? "XML Found" : "XML NOT found");

        if (!xmlInput || !xmlInput.files || xmlInput.files.length === 0) {
            alert("The XML file is strictly mandatory to build a package.");
            return;
        }

        const xmlFile = xmlInput.files[0];
        const pdfFile = pdfInput.files.length > 0 ? pdfInput.files[0] : null;
        const cpFile = cpInput.files.length > 0 ? cpInput.files[0] : null;

        try {
            const xmlBase64 = await SatValidatorQueue._fileToBase64(xmlFile);
            const pdfBase64 = pdfFile ? await SatValidatorQueue._fileToBase64(pdfFile) : false;
            const cpBase64 = cpFile ? await SatValidatorQueue._fileToBase64(cpFile) : false;

            const packageId = 'pkg_' + new Date().getTime();
            const newPackage = {
                id: packageId,
                xml_filename: xmlFile.name,
                xml_file: xmlBase64,
                pdf_filename: pdfFile ? pdfFile.name : '',
                pdf_file: pdfBase64,
                carta_porte_filename: cpFile ? cpFile.name : '',
                carta_porte_file: cpBase64
            };

            SatValidatorQueue.packages.push(newPackage);
            console.log("[DEBUG SAT] -> 6. Package added. Total in queue:", SatValidatorQueue.packages.length);

            const emptyRow = document.getElementById('empty_queue_row');
            if (emptyRow) emptyRow.classList.add('d-none');

            const tbody = document.getElementById('local_package_preview_tbody');
            if (tbody) {
                const tr = document.createElement('tr');
                tr.id = packageId;
                tr.className = 'small-row align-middle';
                tr.innerHTML = `
                    <td class="ps-3 fw-bold text-truncate" style="max-width: 250px;"><i class="fa fa-file-code-o text-danger me-1"/> ${newPackage.xml_filename}</td>
                    <td class="text-muted text-truncate" style="max-width: 200px;">${newPackage.pdf_filename ? '<i class="fa fa-file-pdf-o text-danger me-1"/> ' + newPackage.pdf_filename : '<span class="text-light-muted">-</span>'}</td>
                    <td class="text-muted text-truncate" style="max-width: 200px;">${newPackage.carta_porte_filename ? '<i class="fa fa-truck text-primary me-1"/> ' + newPackage.carta_porte_filename : '<span class="text-light-muted">-</span>'}</td>
                    <td class="text-center">
                        <button type="button" class="btn btn-sm btn-link text-danger remove-package-btn py-0 px-2" data-id="${packageId}">
                            <i class="fa fa-trash-o"/> Delete
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
                console.log("[DEBUG SAT] -> 7. Row successfully injected into the table.");
            } else {
                console.error("[DEBUG SAT] -> CRITICAL: The '#local_package_preview_tbody' container was not found in the DOM.");
            }

            // Reset form inputs
            xmlInput.value = '';
            pdfInput.value = '';
            cpInput.value = '';

            const validateBtn = document.getElementById('validate_all_packages_btn');
            if (validateBtn) validateBtn.removeAttribute('disabled');

        } catch (err) {
            console.error("[DEBUG SAT] -> Critical error during Base64 file conversion:", err);
        }
    }

    // -------------------------------------------------------------------------
    // CASE 2: CLICK ON "DELETE" BUTTON INSIDE THE TABLE (.remove-package-btn)
    // -------------------------------------------------------------------------
    const removeBtn = ev.target.closest('.remove-package-btn');
    if (removeBtn) {
        ev.preventDefault();
        const packageId = removeBtn.getAttribute('data-id');
        console.log("[DEBUG SAT] -> Removing package from queue:", packageId);

        SatValidatorQueue.packages = SatValidatorQueue.packages.filter(pkg => pkg.id !== packageId);

        const row = document.getElementById(packageId);
        if (row) row.remove();

        if (SatValidatorQueue.packages.length === 0) {
            const emptyRow = document.getElementById('empty_queue_row');
            if (emptyRow) emptyRow.classList.remove('d-none');
            const validateBtn = document.getElementById('validate_all_packages_btn');
            if (validateBtn) validateBtn.setAttribute('disabled', 'disabled');
        }
    }

    // -------------------------------------------------------------------------
    // CASE 3: CLICK ON "VALIDATE & PROCESS QUEUE" BUTTON (#validate_all_packages_btn)
    // -------------------------------------------------------------------------
    if (ev.target && ev.target.matches('#validate_all_packages_btn')) {
        ev.preventDefault();
        const button = ev.target;
        const purchaseOrderId = parseInt(button.getAttribute('data-order-id'), 10);
        const resultContainer = document.getElementById('xml_validation_result');

        if (SatValidatorQueue.packages.length === 0) {
            console.warn("[DEBUG SAT] -> Attempted to send an empty queue.");
            return;
        }

        console.log("[DEBUG SAT] -> 8. Initializing bulk transmission. Purchase Order ID:", purchaseOrderId);
        console.log("[DEBUG SAT] -> 9. Exact payload being sent to the backend:", {
            purchase_order_id: purchaseOrderId,
            packages_count: SatValidatorQueue.packages.length,
            packages: SatValidatorQueue.packages
        });

        button.setAttribute('disabled', 'disabled');
        button.innerHTML = `<i class="fa fa-spinner fa-spin me-1"/> Processing Queue...`;

        if (resultContainer) {
            resultContainer.innerHTML = `
                <div class="alert alert-warning py-2 small shadow-sm mb-0">
                    <i class="fa fa-refresh fa-spin me-2"/> Sending packages to server. Processing XMLs and workflows...
                </div>
            `;
        }

        // Native HTTP POST call structured under Odoo's JSON-RPC specification
        fetch("/my/purchase/upload_sat_packages_queue", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                jsonrpc: "2.0",
                params: {
                    purchase_order_id: purchaseOrderId,
                    packages: SatValidatorQueue.packages
                }
            })
        })
        .then(res => {
            console.log("[DEBUG SAT] -> 10. HTTP Status received from server:", res.status);
            return res.json();
        })
        .then(data => {
            console.log("[DEBUG SAT] -> 11. Raw data returned by the server:", data);

            if (data.error) {
                console.error("[DEBUG SAT] -> CRITICAL! Odoo Backend threw an exception:", data.error);
                throw new Error(data.error.message || "Internal Odoo server error.");
            }

            const response = data.result;
            if (response && response.success) {
                console.log("[DEBUG SAT] -> 12. Absolute success reported by the controller.");
                if (resultContainer) {
                    resultContainer.innerHTML = `
                        <div class="alert alert-success py-2 small shadow-sm mb-0">
                            <i class="fa fa-check-circle me-2"/> <strong>Success!</strong> ${response.message || 'All packages processed successfully.'}
                        </div>
                    `;
                }

                // --- ACCESSIBILITY FIX: NATIVE MODAL CLOSING WITHOUT GLOBAL BOOTSTRAP OBJECT ---
                const modalEl = document.getElementById('modal_upload_sat_packages');
                if (modalEl) {
                    // Trigger click on the built-in close button to allow Bootstrap to handle the cleanup
                    const closeButton = modalEl.querySelector('[data-bs-dismiss="modal"]');
                    if (closeButton) {
                        closeButton.click();
                    } else {
                        // Fallback: Manually clear classes and layout state if the button is missing
                        modalEl.classList.remove('show');
                        modalEl.style.display = 'none';
                        document.body.classList.remove('modal-open');
                        const backdrop = document.querySelector('.modal-backdrop');
                        if (backdrop) backdrop.remove();
                    }
                }
                // -------------------------------------------------------------------------------

                // Allow 1.5 seconds for the user to see the green success banner before refreshing
                setTimeout(() => {
                    window.location.reload();
                }, 1500);

            } else {
                console.warn("[DEBUG SAT] -> 13. Server responded but returned success: false", response);
                throw new Error((response && response.error) || "An unexpected error occurred while processing the batch.");
            }
        })
        .catch(error => {
            console.error("[DEBUG SAT] -> 14. Final error catch in the fetch process:", error);
            button.removeAttribute('disabled');
            button.innerHTML = `<i class="fa fa-check-circle me-1"/> Validate &amp; Process Queue`;
            if (resultContainer) {
                resultContainer.innerHTML = `
                    <div class="alert alert-danger py-2 small shadow-sm mb-0">
                        <i class="fa fa-exclamation-triangle me-2"/> <strong>Server Error:</strong> ${error.message || error}
                    </div>
                `;
            }
        });
    }
});