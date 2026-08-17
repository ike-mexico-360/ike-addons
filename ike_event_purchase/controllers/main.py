from odoo.tools import SQL
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

                if customer_product_id.x_sap_code_outgoing != outgoing_sap_code:
                    continue

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
        line_results = sap_object.get('toPurchaseOrderItem', {}).get('results', [])

        # Buscar projecto por codigo de APP
        project_id = request.env['project.project'].search([
            ('name', '=', app_code),
            ('x_purchase_order_sequence_id', '!=', False)
        ], limit=1)
        if not project_id:
            raise NotFound(_("Project '%s' not found or sequence not set") % app_code)

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

        # Buscar sub servicio por código SAP
        po_sub_service_id = request.env['product.product']
        temporal_products = {}
        order_line = []
        event_names = []
        for index, line in enumerate(line_results):
            incoming_sap_code = line.get('supplierMaterialNumber', '').strip()
            outgoing_sap_code = line.get('material', '').strip()
            order_quantity_raw = line.get('orderQuantity', '').strip()
            net_price_raw = line.get('netPriceAmount', '').strip()
            uom = line.get('purchaseOrderQuantityUnit', '').strip()
            event_name = line.get('expediente', '').strip()

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
            product = temporal_products[product_key]

            if not po_sub_service_id:
                po_sub_service_id = product

            if not product:
                raise NotFound(
                    f"No product found for customer {customer_code} and SAP code incoming "
                    f"{incoming_sap_code} and SAP code outgoing {outgoing_sap_code}"
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
                "x_sap_code_outgoing": outgoing_sap_code,
                "x_parent_expedient": event_name,
                "x_external_api_record": True,  # Flag para diferenciar las órdenes de compra externas
            }))

            if event_name not in event_names:
                event_names.append(event_name)

        if not order_line:
            raise NotFound("No lines found at matching supplier product.")

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
            "x_sub_service_id": po_sub_service_id,
            "x_record_tenant": tenant,
            "x_app_code": app_code,
            "x_sap_company_code": company_code,
            "x_invoice_company_id": x_invoice_company_id.id,
            "x_sap_document_currency": currency,
            "x_external_api_record": True,  # Flag para diferenciar las órdenes de compra externas
            "x_external_body": kw,
            "x_origin_events": ", ".join(event_names),
        }

        _logger.info(po_vals)
        PurchaseOrder = request.env['purchase.order'].sudo()
        order_id = PurchaseOrder.create([po_vals])

        return {
            'order_id': order_id.id,
            'order_name': order_id.name,
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

        for field in [
            'companyCode',
            'supplier',
            'documentCurrency',
            'copago',
            'incotermsLocation1',
            'incotermsLocation2',
        ]:
            if not isinstance(sap.get(field), str):
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
        }
        required = {
            'supplierMaterialNumber',
            'orderQuantity',
            'netPriceAmount',
            'material',
            'expediente',
        }

        self._validate_required_keys(
            item, required, f'params.sap.toPurchaseOrderItem.results[{index}]'
        )
        self._validate_no_extra_keys(
            item, allowed, f'params.sap.toPurchaseOrderItem.results[{index}]'
        )

        string_fields = [
            'supplierMaterialNumber',
            'orderQuantity',
            'netPriceAmount',
            'material',
            'expediente',
        ]
        for field in string_fields:
            value = item.get(field)
            if not isinstance(value, str) or not value.strip():
                raise BadRequest(
                    f"params.sap.toPurchaseOrderItem.results[{index}].{field} debe ser string y obligatorio."
                )

        # ToDo: Considerar manejar una lista de campos opcionales
        # Campo opcional: si llega, debe ser string
        if 'purchaseOrderQuantityUnit' in item and item.get('purchaseOrderQuantityUnit') is not None:
            value = item.get('purchaseOrderQuantityUnit')
            if not isinstance(value, str):
                raise BadRequest(
                    f"params.sap.toPurchaseOrderItem.results[{index}].purchaseOrderQuantityUnit debe ser string."
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
