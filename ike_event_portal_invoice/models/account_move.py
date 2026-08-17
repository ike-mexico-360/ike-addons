# -*- coding: utf-8 -*-
import base64
# import json
import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import requests

from odoo import _, models, fields
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    x_payment_receipt_file = fields.Binary(
        string='Payment Receipt',
        attachment=True,
        help='Upload the payment receipt or proof of payment for this invoice.'
    )
    x_payment_receipt_filename = fields.Char(
        string='Payment Receipt Filename'
    )

    x_payment_receipt_file = fields.Binary(
        string='Payment Receipt',
        attachment=True,
        help='Upload the payment receipt or proof of payment for this invoice.'
    )
    x_payment_receipt_filename = fields.Char(
        string='Payment Receipt Filename'
    )
    x_sap_reference_received = fields.Boolean(string='SAP Reference Received', default=False)
    x_sap_connection_error_message = fields.Char(string='SAP Connection Error Message')

    def x_get_name_invoice_report(self):
        """Return the custom portal invoice report template for this module."""
        self.ensure_one()
        return 'ike_event_portal_invoice.custom_report_invoice_document'

    def x_send_supplier_invoice(self):
        """
        Envía la factura de proveedor al endpoint externo definido en parámetros
        de sistema.

        Consideraciones:
        - Solo permite facturas de proveedor publicadas.
        - Lee URL, usuario, contraseña desde ir.config_parameter.
        - Valida presencia de PDF y datos mínimos requeridos por el servicio.
        - Envía payload JSON con autenticación básica.
        - Interpreta respuestas exitosas y de error del servicio.
        - Registra información útil en el chatter y en logs técnicos.

        Parámetros de sistema esperados:
        - ike_event_portal.invoice.endpoint_url
        - ike_event_portal.invoice.username
        - ike_event_portal.invoice.password
        - ike_event_portal.invoice.timeout   (opcional, default 30)
        """
        for move in self:
            move._x_validate_supplier_invoice_ready_to_send()

            config = move._x_get_supplier_invoice_service_config()
            payload = move._x_build_supplier_invoice_payload()
            timeout = config["timeout"]

            self._logger_for_debug_payload(payload)

            try:
                response = requests.post(
                    config["endpoint_url"],
                    json=payload,
                    auth=(config["username"], config["password"]),
                    headers={
                        "Content-Type": "application/json; charset=UTF-8",
                        "Accept": "application/json",
                    },
                    timeout=timeout,
                )
            except requests.exceptions.Timeout as exc:
                _logger.exception(
                    "Timeout enviando factura %s al servicio de proveedor.",
                    move.name or move.id,
                )
                raise UserError(_(
                    "No fue posible enviar la factura porque el servicio tardó "
                    "demasiado en responder."
                )) from exc
            except requests.exceptions.ConnectionError as exc:
                _logger.exception(
                    "Error de conexión enviando factura %s al servicio de proveedor.",
                    move.name or move.id,
                )
                raise UserError(_(
                    "No fue posible conectar con el servicio de facturas de proveedor. "
                    "Verifica la URL, red o VPN."
                )) from exc
            except requests.exceptions.RequestException as exc:
                _logger.exception(
                    "Error HTTP enviando factura %s al servicio de proveedor.",
                    move.name or move.id,
                )
                raise UserError(_(
                    "Ocurrió un error técnico al intentar enviar la factura al servicio externo."
                )) from exc

            result = move._x_process_supplier_invoice_response(response)

            supplier_invoice = result.get("supplier_invoice", False)
            if supplier_invoice:
                # supplier_year = result.get("supplier_year")
                move.write({
                    "x_ref_sap": supplier_invoice,
                    "x_sap_reference_received": True,
                    "x_sap_connection_error_message": "",
                })
            else:
                try:
                    errors = result.get("response_errors", [])
                    error_messages = []
                    if errors:
                        for error in errors:
                            po_number = error.get("Id", "unknown PO number")
                            error_description = error.get("Descripcion", "")
                            error_messages.append(f"{po_number}: {error_description}")
                    else:
                        error_messages.append(_("Error al enviar factura al servicio de proveedor."))
                    move.write({
                        "x_sap_connection_error_message": '\n'.join(error_messages),
                        "x_sap_reference_received": False,
                    })
                except Exception as e:
                    _logger.warning(f'AM-SAP: Error al guardar el log de error (account.move): {str(e)}')

            move.message_post(
                body=_(
                    "Factura enviada al servicio externo correctamente.<br/>"
                    "<b>Documento Odoo:</b> %(move)s<br/>"
                    "<b>Folio externo:</b> %(external)s"
                ) % {
                    "move": move.name or move.id,
                    "external": result.get("supplier_invoice") or _("Sin folio devuelto"),
                }
            )

        return True

    def _logger_for_debug_payload(self, payload):
        def _get_compressed_text(text):
            if not text:
                return ''
            return f"{text[:100]}...{text[-100:]}"

        new_payload = payload.copy()
        xml = new_payload['xml']
        pdf = new_payload['pdf']
        carta_porte = new_payload['carta_porte']

        new_payload['xml'] = _get_compressed_text(xml)
        new_payload['pdf'] = _get_compressed_text(pdf)
        new_payload['carta_porte'] = _get_compressed_text(carta_porte)

        _logger.info(f"AM-SAP: Payload: {new_payload}")

    def _x_get_supplier_invoice_service_config(self):
        """
        Obtiene y valida la configuración del servicio desde parámetros del sistema.
        """
        self.ensure_one()

        icp = self.env["ir.config_parameter"].sudo()

        endpoint_url = (icp.get_param("ike_event_portal.invoice.endpoint_url") or "").strip()
        username = (icp.get_param("ike_event_portal.invoice.username") or "").strip()
        password = (icp.get_param("ike_event_portal.invoice.password") or "").strip()
        timeout_raw = (icp.get_param("ike_event_portal.invoice.timeout") or "30").strip()

        missing_params = []
        if not endpoint_url:
            missing_params.append("ike_event_portal.invoice.endpoint_url")
        if not username:
            missing_params.append("ike_event_portal.invoice.username")
        if not password:
            missing_params.append("ike_event_portal.invoice.password")

        if missing_params:
            raise ValidationError(_(
                "Faltan parámetros de configuración del servicio:\n- %s"
            ) % "\n- ".join(missing_params))

        try:
            timeout = int(timeout_raw)
            if timeout <= 0:
                raise ValueError()
        except ValueError as exc:
            raise ValidationError(_(
                "El parámetro ike_event_portal.invoice.timeout debe ser un entero mayor a 0."
            )) from exc

        return {
            "endpoint_url": endpoint_url,
            "username": username,
            "password": password,
            "timeout": timeout,
        }

    def _x_validate_supplier_invoice_ready_to_send(self):
        """
        Valida que la factura tenga toda la información mínima necesaria antes del envío.
        """
        self.ensure_one()

        if self.move_type != "in_invoice":
            raise ValidationError(_(
                "Solo se pueden enviar facturas de proveedor."
            ))

        if self.state != "posted":
            raise ValidationError(_(
                "La factura debe estar publicada antes de enviarse."
            ))

        if not self.partner_id:
            raise ValidationError(_(
                "La factura no tiene proveedor asociado."
            ))

        if not self.company_id:
            raise ValidationError(_(
                "La factura no tiene compañía asociada."
            ))

        if not self.currency_id:
            raise ValidationError(_(
                "La factura no tiene moneda definida."
            ))

        if not self.invoice_date:
            raise ValidationError(_(
                "La factura debe tener fecha de factura."
            ))

        if not self.ref:
            raise ValidationError(_(
                "La factura debe tener referencia de proveedor en el campo 'Referencia'."
            ))

        if not self.invoice_line_ids.filtered(lambda line: line.display_type):
            raise ValidationError(_(
                "La factura debe tener al menos una línea contable válida."
            ))

        supplier_number = self._x_get_supplier_number()
        if not supplier_number:
            raise ValidationError(_(
                "No se encontró el número de proveedor requerido para el campo SUPPLIER."
            ))

        company_code = self._x_get_company_code()
        if not company_code:
            raise ValidationError(_(
                "No se encontró el código de sociedad requerido para el campo COMPANY_CODE."
            ))

        self._x_validate_reference_length()
        self._x_validate_amount_format()
        self._x_validate_miro_items()

        # Validate at final, to avoid generating the files if the validation fails
        pdf_b64 = self._x_get_invoice_pdf_base64()
        if not pdf_b64:
            raise ValidationError(_(
                "No fue posible generar o recuperar el PDF de la factura."
            ))

        xml_b64 = self._x_get_invoice_xml_base64()
        if not xml_b64:
            raise ValidationError(_(
                "No se encontró el XML de la factura. El servicio lo requiere."
            ))

    def _x_build_supplier_invoice_payload(self):
        """
        Construye el payload JSON conforme al contrato del servicio.
        """
        self.ensure_one()

        amount = self._x_format_decimal(self.amount_total)
        pdf_b64 = self._x_get_invoice_pdf_base64()
        xml_b64 = self._x_get_invoice_xml_base64()

        payload = {
            "id_ike360": str(self.id),
            "company_code": self._x_get_company_code(),
            "supplier": self._x_get_supplier_number(),
            "reference": self.ref.strip() or "",
            "mx_uuid": self._x_get_mx_uuid() or "",
            "gross_amount": amount,
            "currency": (self.currency_id.name or "").strip(),
            "xml": xml_b64,
            "pdf": pdf_b64,
            "miro_items": {
                "items": self._x_build_miro_items(),
            },
            "carta_porte": "",
        }

        carta_porte_b64 = self._x_get_carta_porte_base64()
        if carta_porte_b64:
            payload["carta_porte"] = carta_porte_b64

        return payload

    def _x_process_supplier_invoice_response(self, response):
        """
        Procesa la respuesta del servicio y genera errores funcionales claros.
        """
        self.ensure_one()

        status_code = response.status_code
        response_text = response.text or ""

        try:
            data = response.json() if response_text else {}
        except ValueError:
            data = {}

        if status_code == 200:
            supplier_invoice = data.get("SupplierInvoice", "").strip()
            suplier_year = data.get("SuppInv_Year", "").strip()
            response_errors = data.get("Error", [])
            if not supplier_invoice:
                _logger.warning(
                    "AM-SAP: Respuesta exitosa sin SupplierInvoice. Move=%s Response=%s",
                    self.name or self.id,
                    response_text,
                )
            # if not suplier_year:
            #     _logger.warning(
            #         "Respuesta exitosa sin SuppInv_Year. Move=%s Response=%s",
            #         self.name or self.id,
            #         response_text,
            #     )
            return {
                "supplier_invoice": supplier_invoice,
                "supplier_year": suplier_year,
                "response_errors": response_errors,
                "raw": data,
            }

        error_message = self._x_extract_service_error_message(data, response_text, status_code)

        _logger.error(
            "Error al enviar factura %s. HTTP=%s Response=%s PayloadRef=%s",
            self.name or self.id,
            status_code,
            response_text,
            self.ref,
        )

        raise UserError(error_message)

    def _x_extract_service_error_message(self, data, response_text, status_code):
        """
        Extrae un mensaje legible desde la respuesta del servicio.
        """
        self.ensure_one()

        if isinstance(data, dict):
            errors = data.get("Error")
            if isinstance(errors, list) and errors:
                lines = []
                for err in errors:
                    if not isinstance(err, dict):
                        continue
                    err_id = err.get("id") or _("Sin identificador")
                    description = err.get("Descripcion") or err.get("Description") or _("Sin descripción")
                    lines.append("- %s: %s" % (err_id, description))
                if lines:
                    return _(
                        "El servicio rechazó la factura con los siguientes errores:\n%s"
                    ) % "\n".join(lines)

            message = data.get("message") or data.get("Message")
            if message:
                return _(
                    "El servicio devolvió un error (HTTP %(code)s): %(message)s"
                ) % {
                    "code": status_code,
                    "message": message,
                }

        return _(
            "El servicio devolvió un error HTTP %(code)s.\nRespuesta: %(response)s"
        ) % {
            "code": status_code,
            "response": response_text[:1000] or _("Sin contenido"),
        }

    def _x_get_invoice_pdf_base64(self):
        """
        Genera el PDF de la factura y lo devuelve en Base64.
        """
        self.ensure_one()

        if not self.x_vendor_bill_pdf_file:
            return ""

        return self.x_vendor_bill_pdf_file.decode("ascii") if isinstance(self.x_vendor_bill_pdf_file, bytes) else self.x_vendor_bill_pdf_file

    def _x_get_invoice_xml_base64(self):
        """
        Obtiene el XML adjunto a la factura.

        Nota:
        Este método asume que el XML ya fue generado/adjuntado por la localización
        o por un proceso previo..
        """
        self.ensure_one()

        if not self.xml_file:
            return ""
        return self.xml_file.decode("ascii") if isinstance(self.xml_file, bytes) else self.xml_file

    def _x_get_carta_porte_base64(self):
        """
        Obtiene un archivo Carta Porte en Base64 si existe como adjunto.

        Nota: Pendiente de implementar.
        """
        self.ensure_one()

        # ToDo: Implement
        # attachment = self.env["ir.attachment"].search([
        #     ("res_model", "=", self._name),
        #     ("res_id", "=", self.id),
        #     ("name", "ilike", "carta porte"),
        # ], limit=1, order="id desc")

        # return attachment.datas if attachment and attachment.datas else False
        return False

    def _x_get_supplier_number(self):
        """
        Obtiene la referencia SAP del proveedor.

        - partner_id.x_ref_sap
        """
        self.ensure_one()

        ref_sap = self.partner_id.x_ref_sap
        return (ref_sap or "").strip()

    def _x_get_company_code(self):
        """
        Obtiene el código de sociedad requerido por el servicio.

        Accede a la orden de compra asociada y obtiene el código de sociedad.

        - order_id.x_invoice_company_id.name or ""
        """
        self.ensure_one()

        source_orders = self.line_ids.purchase_line_id.order_id
        if len(source_orders) > 1:
            order_id = source_orders[0]
        elif len(source_orders) == 1:
            order_id = source_orders
        else:
            order_id = self.purchase_id
        return order_id.x_invoice_company_id.name or ""

    def _x_get_mx_uuid(self):
        """
        Obtiene el UUID si existe.

        - Aplica solo a México.
        """
        self.ensure_one()

        mx_uuid = self.env['ir.config_parameter'].sudo().get_param('ike_event_portal.invoice.mx_uuid')
        if mx_uuid:
            return mx_uuid
        return ""

    def _x_build_miro_items(self):
        """
        Construye las líneas MIRO requeridas por el servicio.

        Esta implementación asume que cada línea factura referencia una línea de compra.
        """
        self.ensure_one()

        items = []
        auxiliar_count = 0
        invoice_lines = self.invoice_line_ids.filtered(lambda line: line.display_type).sorted('id')

        for line in invoice_lines:
            purchase_line = line.purchase_line_id
            if not purchase_line:
                raise ValidationError(_(
                    "La línea '%(line)s' no está vinculada a una línea de compra. "
                    "El servicio requiere PO_NUMBER y PO_ITEM."
                ) % {
                    "line": line.name or line.id,
                })

            po_number = (purchase_line.order_id.x_ref_sap or "").strip()
            po_item = str(int(purchase_line.sequence)).zfill(5) if purchase_line.sequence else False
            material = (purchase_line.x_sap_code_income or "").strip()
            expedient = (purchase_line.x_parent_expedient or "").strip()
            quantity = self._x_format_decimal(line.quantity)
            order_unit = (line.product_uom_id.name or "SER").strip()
            net_price = self._x_format_decimal(line.price_unit)

            missing = []
            if not po_number:
                missing.append("PO_NUMBER")
            if not po_item:
                missing.append("PO_ITEM")
            if not expedient:
                missing.append("EXPEDIENT")
            if not material:
                missing.append("MATERIAL")
            if not quantity:
                missing.append("QUANTITY")
            if not order_unit:
                missing.append("ORDER_UNIT")
            if not net_price:
                missing.append("NET_PRICE")

            if missing:
                raise ValidationError(_(
                    "La línea '%(line)s' no cuenta con los datos requeridos para MIRO_ITEMS:\n- %(fields)s"
                ) % {
                    "line": line.name or line.id,
                    "fields": "\n- ".join(missing),
                })

            auxiliar_count += 10
            items.append({
                "po_number": po_number,  # Compra
                "po_item": auxiliar_count,  # Counter 10, 20, 30, etc
                "expedient": expedient,  # Compra
                "material": material,  # Compra
                "quantity": quantity,  # Factura
                "order_unit": "SER",
                "net_price": net_price,  # Factura
            })

        if not items:
            raise ValidationError(_(
                "No hay líneas válidas para construir MIRO_ITEMS."
            ))

        return items

    def _x_validate_miro_items(self):
        """
        Fuerza la validación de las líneas MIRO construyéndolas previamente.
        """
        self.ensure_one()
        self._x_build_miro_items()

    def _x_validate_reference_length(self):
        """
        El servicio define REFERENCE como String(16).
        """
        self.ensure_one()

        reference = (self.ref or "").strip()
        if len(reference) > 16:
            raise ValidationError(_(
                "La referencia del proveedor no puede exceder 16 caracteres. "
                "Valor actual: '%s'"
            ) % reference)

    def _x_validate_amount_format(self):
        """
        Valida que el monto total pueda representarse como decimal positivo.
        """
        self.ensure_one()

        try:
            amount = Decimal(str(self.amount_total))
        except (InvalidOperation, TypeError) as exc:
            raise ValidationError(_(
                "El importe total de la factura no es válido para el envío."
            )) from exc

        if amount <= 0:
            raise ValidationError(_(
                "El importe total de la factura debe ser mayor a cero."
            ))

    def _x_format_decimal(self, value):
        """
        Convierte un valor numérico a string decimal sin separador de miles
        y siempre con 2 decimales.
        """
        if value is None:
            return False

        try:
            amount = Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError):
            raise ValidationError(_(
                "No fue posible convertir un importe a formato decimal válido."
            ))

        return format(amount, "f")
