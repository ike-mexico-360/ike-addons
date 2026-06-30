/** @odoo-module **/

import { rpc } from "@web/core/network/rpc";

document.addEventListener("click", async function (ev) {
    const button = ev.target.closest("#validate_xml_btn");

    if (!button) {
        return;
    }

    try {
        const fileInput = document.getElementById("xml_file");

        if (!fileInput || !fileInput.files.length) {
            alert("Please select an XML file.");
            return;
        }

        let purchaseOrderId = button.getAttribute("data-order-id");

        if (!purchaseOrderId) {
            const match = window.location.pathname.match(/\/my\/purchase\/(\d+)/);
            if (match) {
                purchaseOrderId = match[1];
            }
        }

        if (!purchaseOrderId) {
            alert("Error: Purchase Order ID could not be determined.");
            return;
        }

        const file = fileInput.files[0];
        const reader = new FileReader();

        reader.onload = async function () {
            try {
                const base64 = reader.result.split(",")[1];

                const response = await rpc(
                    "/my/purchase/validate_xml",
                    {
                        xml_file: base64,
                        filename: file.name,
                        purchase_id: parseInt(purchaseOrderId, 10),
                    }
                );

                const resultDiv = document.getElementById("xml_validation_result");

                if (response.success) {
                    const alertClass = response.state === "xml_error" || response.state === "error"
                        ? "alert-danger"
                        : "alert-success";

                    resultDiv.innerHTML = `
                        <div class="alert ${alertClass} mt-3">
                            <strong>Status:</strong> ${response.state}<br/>
                            <strong>SAT Status:</strong> ${response.sat_status}<br/>
                            <strong>Log:</strong> ${response.validation_log}
                        </div>
                    `;
                    // Notificar al componente OWL para que recargue los datos
                    document.dispatchEvent(new CustomEvent("xml_validated", {
                        detail: { sat_status: response.sat_status }
                    }));
                } else {
                    resultDiv.innerHTML = `
                        <div class="alert alert-danger mt-3">
                            <strong>Error:</strong> ${response.validation_log}
                        </div>
                    `;
                }

            } catch (e) {
                console.error("Error during XML validation RPC request:", e);
            }
        };

        reader.readAsDataURL(file);

    } catch (e) {
        console.error("Critical error in click event handler:", e);
    }
});