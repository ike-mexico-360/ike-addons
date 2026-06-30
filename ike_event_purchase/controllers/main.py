# from odoo.tools import SQL
from odoo import http, fields, _, Command
from odoo.http import request
# from odoo.tools import html2plaintext
# from odoo.exceptions import ValidationError
from datetime import timedelta
from werkzeug.exceptions import (BadRequest, NotFound)  # type: ignore
import logging

_logger = logging.getLogger(__name__)


class CatalogsAPIController(http.Controller):
    @http.route('/ike/purchase/create', type='json', auth='user', methods=['POST'])
    def ike_purchase_create(self, **kw):
        self._validate_purchase_params(kw)

        identifier_object = kw.get('identifier', {})
        sap_object = kw.get('sap', {})

        # identifier data
        tenant = identifier_object.get('tenants', '')
        app_code = identifier_object.get('app', '')

        # SAP data
        company_code = sap_object.get('companyCode', '')
        supplier_code = sap_object.get('supplier', '')
        currency = sap_object.get('documentCurrency', '')
        client_code = sap_object.get('incotermsLocation1', '')
        line_results = sap_object.get('toPurchaseOrderItem', {}).get('results', [])

        # Buscar proveedor por código SAP
        supplier_id = request.env['res.partner'].search([
            ('x_ref_sap', '=', supplier_code),
            ('x_is_supplier', '=', True)
        ], limit=1)
        if not supplier_id:
            raise NotFound(_("Supplier '%s' not found") % supplier_code)

        # Buscar sub servicio por código SAP
        SubService = request.env['product.product'].sudo()
        sub_service_domain = SubService.get_subservices_domain()
        po_sub_service_id = request.env['product.product']
        temporal_products = {}
        order_line = []
        event_names = []
        for line in line_results:
            incoming_sap_code = line.get('supplierMaterialNumber', '')
            outgoing_sap_code = line.get('material', '')
            order_quantity = line.get('orderQuantity', 0)
            net_price = line.get('netPriceAmount', 0)
            uom = line.get('purchaseOrderQuantityUnit', '')
            event_name = line.get('expediente', '')

            product_key = f"{incoming_sap_code}&{outgoing_sap_code}"

            if product_key not in temporal_products:
                current_domain = sub_service_domain + [
                    ('x_sap_code_income', '=', incoming_sap_code),
                    ('x_sap_code_outgoing', '=', outgoing_sap_code),
                ]
                product_id = SubService.search(current_domain, limit=1)
                temporal_products[product_key] = product_id.id
            product = temporal_products[product_key]

            if not po_sub_service_id:
                po_sub_service_id = product

            if not product:
                raise NotFound(f"No product found for SAP code {incoming_sap_code} and {outgoing_sap_code}")

            uom_id = self._get_uom_id(uom)

            order_line.append(Command.create({
                "product_id": product,
                "product_qty": order_quantity,
                "price_unit": net_price,
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
            "partner_id": supplier_id.id,
            "company_id": request.env.company.id,
            "date_order": fields.Datetime.now() + timedelta(hours=max_hours_to_confirm),
            "order_line": order_line,
            "state": "to_consolidate",
            "x_client_code": client_code,
            "x_sub_service_id": po_sub_service_id,
            "x_record_tenant": tenant,
            "x_app_code": app_code,
            "x_sap_company_code": company_code,
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

        if not isinstance(identifier.get('tenants'), str) or not identifier.get('tenants'):
            raise BadRequest("params.identifier.tenants debe ser string y obligatorio.")

        if not isinstance(identifier.get('app'), str) or not identifier.get('app'):
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

        for index, item in enumerate(results, start=1):
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
        required = allowed

        self._validate_required_keys(
            item, required, f'params.sap.toPurchaseOrderItem.results[{index}]'
        )
        self._validate_no_extra_keys(
            item, allowed, f'params.sap.toPurchaseOrderItem.results[{index}]'
        )

        string_fields = [
            'supplierMaterialNumber',
            'material',
            'purchaseOrderQuantityUnit',
            'expediente',
        ]
        for field in string_fields:
            if not isinstance(item.get(field), str) or not item.get(field):
                raise BadRequest(
                    f"params.sap.toPurchaseOrderItem.results[{index}].{field} debe ser string y obligatorio."
                )

        if not isinstance(item.get('orderQuantity'), (int, float)):
            raise BadRequest(
                f"params.sap.toPurchaseOrderItem.results[{index}].orderQuantity debe ser numérico."
            )

        if not isinstance(item.get('netPriceAmount'), (int, float)):
            raise BadRequest(
                f"params.sap.toPurchaseOrderItem.results[{index}].netPriceAmount debe ser numérico."
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

    def _get_uom_id(self, uom_name):
        if uom_name == "SER":
            return request.env.ref('l10n_mx.product_uom_service_unit').id

        # Default service
        return request.env.ref('l10n_mx.product_uom_service_unit').id
