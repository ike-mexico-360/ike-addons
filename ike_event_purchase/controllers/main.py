# from odoo.tools import SQL
from odoo import http, fields, _, Command
from odoo.http import request
# from odoo.tools import html2plaintext
# from odoo.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from typing import Any
from werkzeug.exceptions import (  # type: ignore
    BadRequest, Conflict, Forbidden, NotFound, UnprocessableEntity,
)
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class IkePurchaseController(http.Controller):
    # - - - - - - - - - - - - - - #
    #    Create Purchase Order    #
    # - - - - - - - - - - - - - - #
    @http.route('/ike/purchase/create', type='json', auth='user', methods=['POST'])
    def ike_purchase_create(self, **kw):
        def _get_subservice_id(customer_sap_code, incoming_sap_code, outgoing_sap_code):
            """
                Get the subservice

                - client_sap_code: SAP code of the client
                - incoming_sap_code: SAP code of the incoming product
                - outgoing_sap_code: SAP code of the outgoing product
            """
            customer_ids = request.env['product.customerinfo'].sudo().search([
                ('product_code', '=', incoming_sap_code),
                ('partner_id.x_ref_sap', '=', customer_sap_code),
            ])

            product_id = request.env['product.product']
            for customer_id in customer_ids:
                customer_product_id = customer_id.product_id or customer_id.product_tmpl_id.product_variant_id

                if customer_id.partner_id.x_ref_sap != customer_sap_code:
                    continue

                # Integración de homologación al proceos
                matching_homologation_id = customer_product_id.x_product_homologation_model_id.filtered(
                    lambda x: x.x_ref_sap_api == outgoing_sap_code
                )
                if not matching_homologation_id:
                    continue

                # ToDo: Igual integrar que si no está en la homologación, pero el subservicio tiene el código, usarlo
                # if customer_product_id.x_sap_code_outgoing != outgoing_sap_code:
                #     continue

                product_id = customer_product_id
                break

            return product_id

        _logger.warning(kw)

        self._validate_purchase_params(kw)

        identifier_object = kw.get('identifier', {})
        sap_object = kw.get('sap', {})

        # identifier data
        tenant = identifier_object.get('tenants', '').strip()
        app_code = identifier_object.get('app', '').strip()

        # SAP data
        company_code = sap_object.get('companyCode', '').strip()
        supplier_code = sap_object.get('supplier', '').strip()
        currency = sap_object.get('documentCurrency', '').strip()
        customer_code = sap_object.get('incotermsLocation1', '').strip()
        copago = sap_object.get('copago', '').strip()
        event_type = sap_object.get('event_type', '').strip()
        incident_type = sap_object.get('incident_type', '').strip()
        vehicle_weight = sap_object.get('vehicle_weight', '').strip()
        line_results = sap_object.get('toPurchaseOrderItem', {}).get('results', [])

        # Buscar projecto por codigo de APP
        project_id = request.env['project.project'].search([
            ('name', '=', app_code),
            ('x_purchase_order_sequence_id', '!=', False)
        ], limit=1)
        if not project_id:
            raise NotFound(_("Project '%s' not found or sequence not set") % app_code)

        # Event type
        event_type_id = request.env['custom.type.event']
        if event_type:
            if not isinstance(event_type, str):
                raise BadRequest(_("Invalid event type: %s") % event_type)
            event_type_id = event_type_id.search([('ref', '=ilike', event_type)], limit=1)
            if not event_type_id:
                raise NotFound(_("Event type"))

        # Incident type
        incident_type_id = request.env['custom.incident.type']
        if incident_type:
            if not isinstance(incident_type, str):
                raise BadRequest(_("Invalid incident type: %s") % incident_type)
            incident_type_id = incident_type_id.search([('ref', '=ilike', incident_type)], limit=1)
            if not incident_type_id:
                raise NotFound(_("Incident type"))

        # Vehicle weight
        vehicle_weight_id = request.env['custom.vehicle.weight.category']
        if vehicle_weight:
            if not isinstance(vehicle_weight, str):
                raise BadRequest(_("Invalid vehicle weight: %s") % vehicle_weight)
            vehicle_weight_id = vehicle_weight_id.search([('ref', '=ilike', vehicle_weight)], limit=1)
            if not vehicle_weight_id:
                raise NotFound(_("Vehicle weight"))

        # Buscar proveedor por código SAP
        supplier_id = self._find_supplier_or_raise(supplier_code)

        # Buscar cliente por código SAP
        x_customer_id = self._find_customer_or_raise(customer_code)

        # Buscar empresa que factura
        x_invoice_company_id = request.env['res.partner'].search([
            ('name', '=', company_code),
            ('x_is_ike', '=', True)
        ], limit=1)
        if not x_invoice_company_id:
            raise NotFound(_("Company '%s' not found") % company_code)

        # Convertir copago a float
        if copago:
            copago = self._parse_decimal_string(
                copago,
                "params.sap.copago",
                allow_zero=True,
                max_decimals=4,
            )

        # Buscar sub servicio por código SAP
        po_sub_service_id = request.env['product.product']
        outgoing_sap_code_for_homologation = ""
        po_id_event = ""
        po_validador = ""
        temporal_products = {}
        order_line = []
        event_names = []
        for index, line in enumerate(line_results):
            incoming_sap_code = line.get('supplierMaterialNumber', '').strip()
            outgoing_sap_code = line.get('material', '').strip()
            order_quantity_raw = line.get('orderQuantity', '').strip()
            real_outgoing_sap_code = outgoing_sap_code  # Almacenara el valor real del registro en odoo
            net_price_raw = line.get('netPriceAmount', '').strip()
            uom = line.get('purchaseOrderQuantityUnit', '').strip()
            event_name = line.get('expediente', '').strip()
            id_event = line.get('id_evento', '').strip()
            validador = line.get('validador', '').strip()

            order_quantity = self._parse_decimal_string(
                order_quantity_raw,
                f"params.sap.toPurchaseOrderItem.results[{index}].orderQuantity",
                allow_zero=False,
                max_decimals=4,
            )
            net_price = self._parse_decimal_string(
                net_price_raw,
                f"params.sap.toPurchaseOrderItem.results[{index}].netPriceAmount",
                allow_zero=True,
                max_decimals=4,
            )

            product_key = f"{customer_code}&{incoming_sap_code}&{outgoing_sap_code}"

            if product_key not in temporal_products:
                product_id = _get_subservice_id(customer_code, incoming_sap_code, outgoing_sap_code)
                temporal_products[product_key] = product_id.id
                real_outgoing_sap_code = product_id.x_sap_code_outgoing
            product = temporal_products[product_key]

            if not po_sub_service_id:
                po_sub_service_id = po_sub_service_id.browse([product])
            if not outgoing_sap_code_for_homologation:
                outgoing_sap_code_for_homologation = outgoing_sap_code
            if not po_id_event:
                po_id_event = id_event
            if not po_validador:
                po_validador = validador

            if not product:
                raise NotFound(
                    f"No product found for customer {customer_code} and SAP code incoming "
                    f"{incoming_sap_code} and SAP code outgoing {outgoing_sap_code}"
                )
            if not real_outgoing_sap_code:
                raise BadRequest(
                    f"Not product found for outgoing_sap_code {outgoing_sap_code}"
                )

            uom_id = self._get_uom_id(uom)

            order_line_id = request.env['purchase.order.line'].search([
                ('x_parent_expedient', '=', event_name),
                ('order_id.project_id', '=', project_id.id),
            ], limit=1)
            if order_line_id:
                raise BadRequest(
                    "Expedient %s already exists for the project %s in the record [%s] %s" % (event_name, order_line_id.order_id.project_id.name, order_line_id.order_id.name, order_line_id.product_id.name)
                )

            order_line.append(Command.create({
                "product_id": product,
                "product_qty": float(order_quantity),
                "price_unit": float(net_price),
                "currency_id": request.env.company.currency_id.id,
                "product_uom": uom_id,
                "x_sap_code_income": incoming_sap_code,
                "x_sap_code_outgoing": real_outgoing_sap_code,
                "x_parent_expedient": event_name,
                "x_external_api_record": True,  # Flag para diferenciar las órdenes de compra externas
                "x_discount_price": copago,  # Se guarda el copago en la linea
                "x_id_event": id_event,
                "x_validator": validador,
            }))

            if event_name not in event_names:
                event_names.append(event_name)

        if not order_line:
            raise NotFound("No lines found at matching supplier product.")

        # Proceso de homologación en caso de que no se envien los valores de tipo de evento, incidente y categoría de peso
        if not event_type_id or not incident_type_id or not vehicle_weight_id:
            # Obtener linea de homologación
            homologation_id = po_sub_service_id.x_product_homologation_model_id.filtered(
                lambda x: x.x_ref_sap_api == outgoing_sap_code_for_homologation
            )
            if not event_type_id and homologation_id.event_type_id:
                event_type_id = homologation_id.event_type_id
            if not incident_type_id and homologation_id.incident_type_id:
                incident_type_id = homologation_id.incident_type_id
            if not vehicle_weight_id and homologation_id.weight_category_id:
                vehicle_weight_id = homologation_id.weight_category_id

        # Double check
        if event_type and not event_type_id:
            raise UserError(_("No event type found for this product."))
        if incident_type and not incident_type_id:
            raise UserError(_("No incident type found for this product."))
        if vehicle_weight and not vehicle_weight_id:
            raise UserError(_("No vehicle weight found for this product."))

        max_hours_to_confirm = request.env.company.x_time_for_automatic_purchase_generation
        po_vals = {
            "project_id": project_id.id,
            "partner_id": supplier_id.id,
            "company_id": request.env.company.id,
            "date_order": fields.Datetime.now() + timedelta(hours=max_hours_to_confirm),
            "order_line": order_line,
            "state": "to_consolidate",
            # "x_client_code": customer_code,
            "x_customer_id": x_customer_id.id,
            "x_sub_service_id": po_sub_service_id.id,
            "x_record_tenant": tenant,
            "x_app_code": app_code,
            "x_sap_company_code": company_code,
            "x_invoice_company_id": x_invoice_company_id.id,
            "x_sap_document_currency": currency,
            "x_external_api_record": True,  # Flag para diferenciar las órdenes de compra externas
            "x_external_body": kw,
            "x_origin_events": ", ".join(event_names),
            "x_discount_price": copago,  # Se guarda el copago en el header
            "x_event_type_id": event_type_id.id,
            "x_incident_type_id": incident_type_id.id,
            "x_vehicle_weight_category_id": vehicle_weight_id.id,
            "x_id_event": po_id_event,
            "x_validator": po_validador,
        }

        _logger.info(po_vals)
        PurchaseOrder = request.env['purchase.order'].sudo()
        # return {
        #     "Hola": "Adios"
        # }
        order_id = PurchaseOrder.create([po_vals])
        for line in order_id.order_line:
            try:
                line._onchange_x_discount_price()
                line.onchange_x_discount_price()
            except Exception as e:
                _logger.error(f"Error al calcular el copago: {str(e)}")

        return {
            'code': '200',
            'detail': {
                'message': 'OK',
                'purchaseOrder': order_id.name,
            },
        }

    def _validate_purchase_params(self, params):
        if not isinstance(params, dict):
            raise BadRequest("Los params deben ser un objeto JSON.")

        allowed_root = {'identifier', 'sap'}
        required_root = {'identifier', 'sap'}

        self._validate_required_keys(params, required_root, 'params')
        self._validate_no_extra_keys(params, allowed_root, 'params')

        identifier = params.get('identifier')
        sap = params.get('sap')

        if not isinstance(identifier, dict):
            raise BadRequest("params.identifier debe ser un objeto.")
        if not isinstance(sap, dict):
            raise BadRequest("params.sap debe ser un objeto.")

        self._validate_identifier(identifier)
        self._validate_sap(sap)

    def _validate_identifier(self, identifier):
        allowed = {'tenants', 'app'}
        required = {'tenants', 'app'}

        self._validate_required_keys(identifier, required, 'params.identifier')
        self._validate_no_extra_keys(identifier, allowed, 'params.identifier')

        if not isinstance(identifier.get('tenants'), str) or not identifier.get('tenants').strip():
            raise BadRequest("params.identifier.tenants debe ser string y obligatorio.")

        if not isinstance(identifier.get('app'), str) or not identifier.get('app').strip():
            raise BadRequest("params.identifier.app debe ser string y obligatorio.")

    def _validate_sap(self, sap):
        allowed = {
            'companyCode',
            'supplier',
            'documentCurrency',
            'copago',
            'event_type',
            'incident_type',
            'vehicle_weight',
            'incotermsLocation1',
            'incotermsLocation2',
            'toPurchaseOrderItem',
        }
        required = {
            'companyCode',
            'supplier',
            'documentCurrency',
            'copago',
            'incotermsLocation1',
            'incotermsLocation2',
            'toPurchaseOrderItem',
        }

        self._validate_required_keys(sap, required, 'params.sap')
        self._validate_no_extra_keys(sap, allowed, 'params.sap')

        string_fields = [
            'companyCode',
            'supplier',
            'documentCurrency',
            'copago',
            'event_type',
            'incident_type',
            'vehicle_weight',
            'incotermsLocation1',
            'incotermsLocation2',
        ]

        for field in string_fields:
            if field in sap and sap[field] is not None:
                if not isinstance(sap[field], str):
                    raise BadRequest(f"params.sap.{field} debe ser string.")

        to_purchase = sap.get('toPurchaseOrderItem')
        if not isinstance(to_purchase, dict):
            raise BadRequest("params.sap.toPurchaseOrderItem debe ser un objeto.")

        allowed_to_purchase = {'results'}
        required_to_purchase = {'results'}

        self._validate_required_keys(
            to_purchase, required_to_purchase, 'params.sap.toPurchaseOrderItem'
        )
        self._validate_no_extra_keys(
            to_purchase, allowed_to_purchase, 'params.sap.toPurchaseOrderItem'
        )

        results = to_purchase.get('results')
        if not isinstance(results, list) or not results:
            raise BadRequest(
                "params.sap.toPurchaseOrderItem.results debe ser una lista con al menos un elemento."
            )

        for index, item in enumerate(results):
            self._validate_result_item(item, index)

    def _validate_result_item(self, item, index):
        if not isinstance(item, dict):
            raise BadRequest(
                f"params.sap.toPurchaseOrderItem.results[{index}] debe ser un objeto."
            )

        allowed = {
            'supplierMaterialNumber',
            'orderQuantity',
            'netPriceAmount',
            'material',
            'purchaseOrderQuantityUnit',
            'expediente',
            'id_evento',
            'validador',
        }
        required = {
            'supplierMaterialNumber',
            'orderQuantity',
            'netPriceAmount',
            'material',
            'expediente',
        }
        string_fields = [
            'supplierMaterialNumber',
            'orderQuantity',
            'netPriceAmount',
            'purchaseOrderQuantityUnit',
            'material',
            'expediente',
            'id_evento',
            'validador',
        ]

        self._validate_required_keys(
            item, required, f'params.sap.toPurchaseOrderItem.results[{index}]'
        )
        self._validate_no_extra_keys(
            item, allowed, f'params.sap.toPurchaseOrderItem.results[{index}]'
        )

        for field in string_fields:
            if field in item and item[field] is not None:
                if not isinstance(item[field], str):
                    raise BadRequest(
                        f"params.sap.toPurchaseOrderItem.results[{index}].{field} debe ser string."
                    )

        self._parse_decimal_string(
            item.get('orderQuantity'),
            f'params.sap.toPurchaseOrderItem.results[{index}].orderQuantity',
            allow_zero=False,
            max_decimals=4,
        )

        self._parse_decimal_string(
            item.get('netPriceAmount'),
            f'params.sap.toPurchaseOrderItem.results[{index}].netPriceAmount',
            allow_zero=True,
            max_decimals=4,
        )

    def _validate_required_keys(self, data, required_keys, path):
        missing = required_keys - set(data.keys())
        if missing:
            raise BadRequest(
                f"Faltan campos obligatorios en {path}: {', '.join(sorted(missing))}"
            )

    def _validate_no_extra_keys(self, data, allowed_keys, path):
        extra = set(data.keys()) - allowed_keys
        if extra:
            raise BadRequest(
                f"Campos no permitidos en {path}: {', '.join(sorted(extra))}"
            )

    def _parse_decimal_string(self, value, field_path, allow_zero=True, max_decimals=4):
        """ Convierte un número enviado como string a Decimal de forma segura. """
        if not isinstance(value, str):
            raise BadRequest(f"{field_path} debe ser string.")

        clean_value = value.strip()
        if not clean_value:
            raise BadRequest(f"{field_path} no puede estar vacío.")

        try:
            decimal_value = Decimal(clean_value)
        except InvalidOperation:
            raise BadRequest(
                f"{field_path} debe contener un número válido en formato texto, por ejemplo '1' o '550.25'."
            )

        if decimal_value.is_nan() or decimal_value.is_infinite():
            raise BadRequest(f"{field_path} contiene un valor no permitido.")

        if allow_zero:
            if decimal_value < 0:
                raise BadRequest(f"{field_path} no puede ser negativo.")
        else:
            if decimal_value <= 0:
                raise BadRequest(f"{field_path} debe ser mayor que 0.")

        exponent = decimal_value.as_tuple().exponent
        decimals = abs(exponent) if exponent < 0 else 0
        if decimals > max_decimals:
            raise BadRequest(
                f"{field_path} no debe tener más de {max_decimals} decimales."
            )

        return decimal_value

    def _get_uom_id(self, uom_name):
        if uom_name == "SER":
            return request.env.ref('l10n_mx.product_uom_service_unit').id

        # Default service
        return request.env.ref('l10n_mx.product_uom_service_unit').id

    # ------------------------- #
    #     Auxiliar methods      #
    # ------------------------- #
    @staticmethod
    def _get_partner_id(ref, partner_type):
        """Validate partner"""
        max_length = 10
        aux_ref = ref.zfill(max_length)
        company_id = request.env.company.id

        allowed_types = {"supplier", "client"}
        if partner_type not in allowed_types:
            raise BadRequest(f"Invalid partner type: {partner_type}")

        field_name = f"x_is_{partner_type}"

        query = """
            SELECT id
            FROM res_partner
            WHERE lpad(x_ref_sap, %s, '0') = %s
            AND disabled = false
            AND {field} = true
            AND (company_id = %s OR company_id IS NULL)
        """.format(field=field_name)

        request.env.cr.execute(query, [max_length, aux_ref, company_id])
        result = [x["id"] for x in request.env.cr.dictfetchall()]

        # hack to show 'customer' string instead of 'client'
        if partner_type == 'client':
            partner_type = 'customer'

        partners = request.env["res.partner"].sudo().browse(result)
        if partners:
            if len(partners) > 1:
                raise Conflict(_(f"Found more than one {partner_type} with ref {ref}"))
            return partners
        raise NotFound(_(f"Not exist {partner_type} with ref {ref}"))

    def _find_supplier_or_raise(self, ref):
        return self._get_partner_id(ref, 'supplier')

    def _find_customer_or_raise(self, ref):
        return self._get_partner_id(ref, 'client')

    # ---------------------------- #
    #      Estados de fatura       #
    # ---------------------------- #
    # Códigos de estado enviados por SAP. Estos códigos no se almacenan en un
    # campo adicional: más adelante se traducen a operaciones nativas de Odoo.
    _ALLOWED_STATUS = frozenset({'0', '1', '2', '8', '9'})

    # El contrato es estricto para detectar nombres incorrectos o información
    # inesperada antes de consultar o modificar registros contables.
    _REQUIRED_FIELDS = frozenset({
        'society', 'idProvider', 'idDocument', 'idDocumentPO', 'status',
    })

    @staticmethod
    def _ensure_api_user_authorized() -> None:
        """Impide que una sesión sin permisos contables modifique facturas."""
        allowed_groups = (
            'account.group_account_invoice',
            'account.group_account_manager',
            'base.group_system',
        )
        if not any(request.env.user.has_group(group) for group in allowed_groups):
            raise Forbidden(
                description=(
                    "El usuario autenticado no tiene permisos de facturación "
                    "para consumir este endpoint."
                )
            )

    @classmethod
    def _ensure_jsonrpc_params_shape(cls, params: dict[str, Any]) -> None:
        """Valida que ``params`` contenga exactamente el contrato de la API."""
        if not isinstance(params, dict):
            raise BadRequest(description="'params' debe ser un objeto JSON.")

        received_fields = set(params)
        missing_fields = cls._REQUIRED_FIELDS - received_fields
        unknown_fields = received_fields - cls._REQUIRED_FIELDS

        if missing_fields:
            missing_list = ', '.join(sorted(missing_fields))
            raise BadRequest(description=f"Faltan campos obligatorios: {missing_list}.")

        if unknown_fields:
            unknown_list = ', '.join(sorted(unknown_fields))
            raise BadRequest(description=f"Se recibieron campos no permitidos: {unknown_list}.")

    @staticmethod
    def _ensure_non_empty_string(value: Any, field_name: str) -> str:
        """Valida y normaliza un identificador de texto recibido por SAP."""
        if not isinstance(value, str):
            raise BadRequest(description=f"El campo '{field_name}' debe ser string.")

        normalized = value.strip()
        if not normalized:
            raise BadRequest(description=f"El campo '{field_name}' no puede estar vacío.")

        return normalized

    @classmethod
    def _validate_status(cls, value: Any) -> str:
        """Comprueba que el código corresponda a un estado soportado."""
        if not isinstance(value, str):
            raise BadRequest(description="El campo 'status' debe ser string.")

        if value not in cls._ALLOWED_STATUS:
            allowed_values = ', '.join(sorted(cls._ALLOWED_STATUS))
            raise UnprocessableEntity(
                description=f"El campo 'status' debe ser uno de: {allowed_values}."
            )

        return value

    @staticmethod
    def _find_purchase_order_or_raise(
        society: str, id_document_po: str, supplier,
    ):
        """Busca y valida la orden usando todos los identificadores recibidos.

        La orden debe pertenecer al proveedor, coincidir con la sociedad SAP y
        estar confirmada. De la misma orden se obtiene la sociedad pagadora que
        se devuelve posteriormente en la respuesta.
        """
        purchase_orders = request.env['purchase.order'].sudo().search([
            ('x_ref_sap', '=', id_document_po),
            ('x_sap_company_code', '=', society),
            ('partner_id', '=', supplier.id),
        ], limit=2)

        if not purchase_orders:
            raise NotFound(
                description=(
                    "No se encontró una orden de compra que coincida con la "
                    "sociedad, el proveedor y la referencia SAP recibidos."
                )
            )
        if len(purchase_orders) > 1:
            raise Conflict(
                description=(
                    "Existe más de una orden de compra con la misma sociedad, "
                    "proveedor y referencia SAP."
                )
            )

        purchase_order = purchase_orders
        if purchase_order.state not in ('purchase', 'done'):
            raise UnprocessableEntity(
                description=(
                    f"La orden de compra '{purchase_order.display_name}' debe estar "
                    "en estado Purchase Order o Locked."
                )
            )

        payer = purchase_order.x_invoice_company_id
        if not payer or not payer.x_is_ike:
            raise UnprocessableEntity(
                description="La orden de compra no tiene una sociedad pagadora IKE válida."
            )
        if payer.x_society_sap and payer.x_society_sap != society:
            raise UnprocessableEntity(
                description=(
                    "La sociedad SAP de la pagadora no coincide con la sociedad "
                    "recibida."
                )
            )

        return purchase_order, payer

    @staticmethod
    def _find_vendor_bill_or_raise(id_document: str, purchase_order, supplier):
        """Localiza la factura del proveedor vinculada a la orden de compra.

        Se filtra sobre ``invoice_ids`` para garantizar que la factura realmente
        pertenezca a la orden encontrada. ``idDocument`` se compara con
        ``account.move.x_ref_sap``.
        """
        bills = purchase_order.invoice_ids.filtered(
            lambda move: (
                move.move_type == 'in_invoice'
                and (move.x_ref_sap or '').strip() == id_document
                and move.partner_id.commercial_partner_id
                == supplier.commercial_partner_id
            )
        )

        if not bills:
            raise NotFound(
                description=(
                    "No se encontró una factura de proveedor relacionada con la "
                    "orden de compra y con "
                    f"x_ref_sap='{id_document}'."
                )
            )
        if len(bills) > 1:
            raise Conflict(
                description=(
                    "Existe más de una factura relacionada con la orden de compra "
                    f"y con x_ref_sap='{id_document}'."
                )
            )
        return bills

    @staticmethod
    def _ensure_bill_posted(move):
        """Deja una factura lista para operaciones contables de pago.

        Odoo solo permite pagar facturas publicadas. Si estaba cancelada se
        restaura primero a borrador y después se publica mediante sus métodos
        estándar, permitiendo que Odoo ejecute todas sus validaciones.
        """
        if move.state == 'cancel':
            move.button_draft()
        if move.state == 'draft':
            move.action_post()

    @classmethod
    def _apply_invoice_status(cls, move, status: str) -> None:
        """Traduce un estado SAP a una transición nativa de factura en Odoo.

        Correspondencia:
            0: En revisión -> borrador.
            1: Aceptada    -> publicada.
            2: Pagada      -> pago completo mediante el asistente estándar.
            8: Rechazada   -> cancelada.
            9: Cancelada   -> cancelada.

        Odoo no tiene un estado contable independiente para "rechazada"; por
        eso los códigos 8 y 9 terminan en ``cancel``. ``x_status_invoice``
        conserva la diferencia entre ambos estados de negocio.
        """
        try:
            if status == '0':
                if move.state != 'draft':
                    move.button_draft()
                    _logger.info(f"AM (status) Move {move.name} draft")
            elif status == '1':
                cls._ensure_bill_posted(move)
                _logger.info(f"AM (status) Move {move.name} bill posted")
            elif status == '2':
                cls._ensure_bill_posted(move)
                if move.payment_state != 'paid':
                    # Se utiliza el mismo asistente que abre el botón
                    # "Registrar pago". Así Odoo crea, publica y concilia el
                    # pago en vez de forzar manualmente ``payment_state``.
                    payment_register = request.env[
                        'account.payment.register'
                    ].sudo().with_context(
                        active_model='account.move',
                        active_ids=move.ids,
                    ).create({})
                    payment_register.action_create_payments()
                move.action_paid()
                _logger.info(f"AM (status) Move {move.name} bill paid")
            elif status == '8':
                if move.state != 'cancel':
                    move.button_cancel()
                move.action_rejected()
                _logger.info(f"AM (status) Move {move.name} bill rejected")
            elif status == '9':
                if move.state != 'cancel':
                    move.button_cancel()
                    _logger.info(f"AM (status) Move {move.name} bill cancel")
                else:
                    move.x_status_invoice = 'cancelled'
                    _logger.info(f"AM (status) Move {move.name} cancelled")
        except (UserError, ValidationError) as error:
            raise UnprocessableEntity(
                description=(
                    f"Odoo no pudo aplicar el estado solicitado a la factura "
                    f"'{move.display_name}': {error}"
                )
            ) from error

    @http.route(
        '/api/sap/document/status',
        type='json',
        # El consumidor debe autenticarse primero en
        # /web/session/authenticate y enviar después la cookie session_id.
        auth='user',
        methods=['POST'],
        csrf=False,
    )
    def sap_document_status(self, **params):
        """Recibe desde SAP el estado de una factura y actualiza Odoo.

        Flujo de consumo:
            1. POST /web/session/authenticate para obtener ``session_id``.
            2. POST /api/sap/document/status enviando esa cookie.
            3. Odoo valida proveedor, orden, pagadora y factura.
            4. Se aplica la transición contable correspondiente.

        Al ser una ruta ``type='json'``, Odoo extrae automáticamente el objeto
        ``params`` del cuerpo JSON-RPC y lo entrega como argumentos nombrados.
        """
        # La cookie demuestra que existe una sesión, pero además exigimos que
        # esa sesión pertenezca a un usuario autorizado para gestionar facturas.
        self._ensure_api_user_authorized()

        # Validar todo el contrato antes de realizar búsquedas o escrituras.
        self._ensure_jsonrpc_params_shape(params)

        _logger.info(f"AM (status) /api/sap/document/status: {params}")

        society = self._ensure_non_empty_string(params.get('society'), 'society')
        id_provider = self._ensure_non_empty_string(params.get('idProvider'), 'idProvider')
        id_document = self._ensure_non_empty_string(params.get('idDocument'), 'idDocument')
        id_document_po = self._ensure_non_empty_string(params.get('idDocumentPO'), 'idDocumentPO')
        status = self._validate_status(params.get('status'))

        # Resolver los documentos en orden evita aceptar una factura que no
        # pertenezca al proveedor, a la sociedad o a la orden informados.
        supplier = self._find_supplier_or_raise(id_provider)
        purchase_order, payer = self._find_purchase_order_or_raise(
            society, id_document_po, supplier,
        )
        move = self._find_vendor_bill_or_raise(id_document, purchase_order, supplier)

        # Guardar el estado anterior permite informar si la petición realmente
        # produjo un cambio y hace que las llamadas repetidas sean observables.
        previous_state = move.state
        previous_payment_status = move.status_in_payment
        self._apply_invoice_status(move, status)
        current_state = move.state
        current_payment_status = move.status_in_payment
        updated = (
            previous_state != current_state
            or previous_payment_status != current_payment_status
        )

        return {
            'society': {
                'id': payer.id,
                'name': payer.name,
                'code': society,
            },
            'provider': {
                'id': supplier.id,
                'name': supplier.name,
                'x_ref_sap': supplier.x_ref_sap,
            },
            'accountMove': {
                'id': move.id,
                'name': move.display_name,
                'ref': move.ref,
                'x_ref_sap': move.x_ref_sap,
            },
            'purchaseOrder': {
                'id': purchase_order.id,
                'name': purchase_order.name,
                'x_ref_sap': purchase_order.x_ref_sap,
            },
            'status': status,
            'previousInvoiceState': previous_state,
            'invoiceState': current_state,
            'previousStatusInPayment': previous_payment_status,
            'statusInPayment': current_payment_status,
            'updated': updated,
            'valid': True,
        }
