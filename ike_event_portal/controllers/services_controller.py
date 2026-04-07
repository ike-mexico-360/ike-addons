from odoo import http, fields
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request
import logging

# from odoo.addons.ike_event_portal.services.notification_service import (
#     NotificationService,
# )

_logger = logging.getLogger(__name__)


class PortalUserAccount(CustomerPortal):
    def _get_ike_event_services_domain(self):
        return []

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "ike_event_service_count" in counters:
            values["ike_event_service_count"] = request.env["ike.event"].search_count(
                self._get_ike_event_services_domain(), limit=1
            )
        return values

    @http.route(
        ["/provider/portal/services", "/provider/portal/services/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_services_list(self, page=1, sortby=None, **kw):
        if not request.env.user.has_group(
            "ike_event_portal.custom_group_portal_supervisor"
        ):
            return request.redirect("/my")

        return request.render("ike_event_portal.portal_ike_event_services")

    @http.route(
        ["/provider/portal/services/supplier_current_notified"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def get_supplier_current_notified(self, supplier_id, **kw):
        """
        Get the currently notified supplier for an event, including
        all event details needed by the frontend in a single response
        to avoid N+1 queries.
        """
        try:
            supplier_lines = request.env["ike.event.supplier.public"].sudo().search(
                [
                    ("supplier_id", "=", supplier_id),
                    ("state", "in", ["notified", "accepted", "assigned"]),
                ],
                order="id DESC",
            )

            if supplier_lines:
                results = []

                user_lang = request.env.user.lang or "es_MX"
                Model = request.env["ike.event.supplier.public"].with_context(
                    lang=user_lang
                )
                state_field = Model._fields["state"]

                # get translate
                state_translations = dict(state_field._description_selection(Model.env))

                # Prefetch all related events in one go via ORM prefetching
                # by accessing the recordset fields within the same loop
                for supplier_line in supplier_lines:
                    event = supplier_line.event_id

                    # Build sub_service display name
                    sub_service_name = ""
                    if event.sub_service_id:
                        sub_service_name = event.sub_service_id.name or ""

                    # Build stage display name with user language
                    stage_name = ""
                    if event.stage_id:
                        stage = event.stage_id.with_context(lang=user_lang)
                        stage_name = stage.name or ""

                    results.append(
                        {
                            "supplier_id": supplier_line.supplier_id.id,
                            "supplier_name": supplier_line.supplier_id.name,
                            "event_supplier_id": supplier_line.id,
                            "event_id": event.id,
                            "truck_id": supplier_line.truck_id.id,
                            "driver_name": (
                                supplier_line.truck_id.driver_id.name
                                if supplier_line.truck_id.driver_id
                                else None
                            ),
                            "truck_name": supplier_line.truck_id.name,
                            "event_supplier_state": supplier_line.state,
                            "event_supplier_state_label": state_translations.get(
                                supplier_line.state, supplier_line.state
                            ),
                            "supplier_link_id": supplier_line.supplier_link_id.id,
                            # Event details (avoids N+1 frontend queries)
                            "event_name": event.name or "",
                            "event_date": (
                                fields.Datetime.to_string(event.event_date)
                                if event.event_date
                                else ""
                            ),
                            "location_label": event.location_label or "",
                            "service_id_label": (
                                event.service_id.name if event.service_id else ""
                            ),
                            "sub_service_id_label": sub_service_name,
                            "stage_id_label": stage_name,
                            "stage": supplier_line.stage_id.name if supplier_line.stage_id else ""
                        }
                    )
                return {"success": True, "suppliers_events": results}

            return {"success": False, "suppliers_events": []}
        except Exception as e:
            _logger.error(f"Error getting current notified supplier: {str(e)}")
            return {"success": False, "error": str(e)}

    @http.route(
        ["/provider/portal/services/supplier_notified_single"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def get_supplier_notified_single(self, event_supplier_id, **kw):
        """
        Get a single notified or accepted supplier event by event_supplier_id
        """
        try:
            if not event_supplier_id:
                return {"success": False, "error": "event_supplier_id is required"}

            supplier_line = request.env["ike.event.supplier.public"].search(
                [
                    ("id", "=", event_supplier_id),
                ],
                limit=1,
            )

            if not supplier_line:
                return {
                    "success": False,
                    "error": "Event supplier not found or not in valid state",
                    "supplier_event": None,
                }

            # Get translated state labelss
            Model = request.env["ike.event.supplier.public"].with_context(
                lang=request.env.user.lang
            )
            state_field = Model._fields["state"]
            state_translations = dict(state_field._description_selection(Model.env))
            result = {
                "supplier_id": supplier_line.supplier_id.id,
                "supplier_name": supplier_line.supplier_id.name,
                "event_supplier_id": supplier_line.id,
                "event_id": supplier_line.event_id.id,
                "truck_id": supplier_line.truck_id.id,
                # "user_id": supplier_line.user_id.id,
                "driver_name": (
                    supplier_line.truck_id.driver_id.name
                    if supplier_line.truck_id.driver_id
                    else None
                ),
                "truck_name": supplier_line.truck_id.name,
                "event_supplier_state": supplier_line.state,
                "event_supplier_state_label": state_translations.get(
                    supplier_line.state, supplier_line.state
                ),
                "event_supplier_summary_data": supplier_line.get_event_supplier_summary_data(),
                "travel_tracking_url": supplier_line.get_travel_tracking_url(),
                "stage": supplier_line.stage_ref,
                "supplier_link_id": supplier_line.supplier_link_id.id,
            }

            return {"success": True, "supplier_event": result}

        except Exception as e:
            _logger.error(f"Error getting single notified supplier: {str(e)}")
            return {"success": False, "error": str(e), "supplier_event": None}

    @http.route(
        ["/provider/portal/services/send_notification"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def send_user_notification(self, vehicle_id, user_id, event_data, **kw):
        """
        Endpoint to send notification via AWS Lambda
        Called from React component
        """
        try:
            # Validate inputs
            if not vehicle_id or not user_id:
                return {
                    "success": False,
                    "error": "vehicle_id and user_id are required",
                }

            url = (
                request.env["ir.config_parameter"]
                .sudo()
                .get_param("ike_event.app.url.notification")
            )
            result = False
            if url:
                event_supplier_id = event_data.get("event_supplier_id")
                try:
                    result = request.env["ike.event.supplier"].operator_app_notify(
                        url,
                        user_id,
                        vehicle_id,
                        event_data.get("service_id"),
                        event_data.get("ca_id"),
                        event_data.get("lat"),
                        event_data.get("lng"),
                        event_data.get("dst_lat"),
                        event_data.get("dst_lng"),
                        event_data.get("control"),
                        event_data.get("assignation_type"),
                        event_data.get("estatus"),
                        event_supplier_id,
                        event_data.get("user_code"),
                    )

                    _logger.info(f"Notify operator by portal -> {result}")
                    # Marcar la linea como notificada
                    request.env["ike.event.supplier"].sudo().browse(
                        event_supplier_id
                    ).notification_sent_to_app = True
                except Exception as e:
                    _logger.error(f"Error notificando al operador: {str(e)}")

                if not result:
                    return {"success": False, "error": "No operatos to notify"}

            # Call the notification service
            # result = NotificationService.send_user_notification(user_id, vehicle_id, event)

            if result:
                return {
                    "success": True,
                    "message": "Notification sent successfully",
                    "data": result,
                }
            else:
                return {"success": False, "error": "Failed to send notification"}

        except Exception as e:
            _logger.error(f"Error in send_user_notification endpoint: {str(e)}")
            return {"success": False, "error": str(e)}

    @http.route(
        ["/provider/portal/services/supplier_cancel"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def supplier_cancel_service(
        self, event_supplier_id, cancel_reason_id=None, reason_text=None, **kw
    ):
        """
        Cancel a service by supplier from the portal
        """
        try:
            if not event_supplier_id:
                return {"success": False, "error": "event_supplier_id is required"}

            if not cancel_reason_id:
                return {"success": False, "error": "cancel_reason_id is required"}

            supplier_line = request.env["ike.event.supplier.public"].browse(
                event_supplier_id
            )

            if not supplier_line.exists():
                return {"success": False, "error": "Service not found"}

            if supplier_line.state not in ("accepted", "assigned"):
                return {
                    "success": False,
                    "error": "Service cannot be cancelled. Only accepted or assigned services can be cancelled.",
                }

            # Call the action_supplier_cancel method
            supplier_line.action_supplier_cancel(
                cancel_reason_id=cancel_reason_id, reason_text=reason_text or ""
            )
            # .with_context(ike_event_action_from="control_panel")

            return {"success": True, "message": "Service cancelled successfully"}

        except Exception as e:
            _logger.error(f"Error cancelling service: {str(e)}")
            return {"success": False, "error": str(e)}

    @http.route(
        ["/provider/portal/services/get_available_concepts"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def get_available_concepts(self, event_id, supplier_id, **kw):
        """
        Get available concepts/products for an event based on the concepts domain
        """
        try:
            if not event_id or not supplier_id:
                return {
                    "success": False,
                    "error": "event_id and supplier_id are required",
                }

            event = request.env["ike.event"].sudo().browse(event_id)
            if not event.exists():
                return {"success": False, "error": "Event not found"}

            # Get the concepts domain from product.product model
            ProductProduct = request.env["product.product"].sudo()
            domain = ProductProduct.get_concepts_domain()
            domain.extend(
                [
                    "|",
                    ("x_apply_all_services_subservices", "=", True),
                    ("x_categ_id", "in", [event.service_id.id, False]),
                    "|",
                    ("x_product_id", "in", [event.sub_service_id.id]),
                    ("x_product_id", "=", False),
                ]
            )

            # Get existing product IDs for this event/supplier to exclude
            existing_products = request.env["ike.event.supplier.product"].sudo().search([
                ('event_id', '=', event_id),
                ('supplier_id', '=', supplier_id),
            ])
            existing_product_ids = existing_products.mapped('product_id').ids

            if existing_product_ids:
                domain.append(('id', 'not in', existing_product_ids))

            # _logger.info(f"Concepts domain for event {event_id}: {alternative_domain}")

            # Search products with the domain
            products = ProductProduct.search_read(
                domain, ["id", "name", "uom_id"], limit=100
            )

            return {
                "success": True,
                "products": products,
            }

        except Exception as e:
            _logger.error(f"Error getting available concepts: {str(e)}")
            return {"success": False, "error": str(e)}

    @http.route(
        ["/provider/portal/services/create_concept"],
        type="json",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def create_concept(self, event_id, supplier_id, product_id, quantity, supplier_link_id, **kw):
        """
        Create a new concept/product for an event supplier and apply onchange logic
        """
        try:
            if not event_id or not supplier_id or not product_id:
                return {
                    "success": False,
                    "error": "event_id, supplier_id and product_id are required",
                }

            EventSupplierProduct = request.env["ike.event.supplier.product"].sudo()
            Product = request.env["product.product"].sudo()

            if not supplier_link_id:
                return {"success": False, "error": "Supplier link ID is required"}

            # Get the product
            product = Product.browse(product_id)
            if not product.exists():
                return {"success": False, "error": "Product not found"}

            # Create the supplier product record with basic fields
            new_concept = EventSupplierProduct.create(
                {
                    "event_supplier_link_id": supplier_link_id,
                    "event_id": event_id,
                    "supplier_id": supplier_id,
                    "product_id": product_id,
                    "estimated_quantity": quantity or 1,
                    "quantity": quantity or 1,
                    "uom_id": product.uom_id.id if product.uom_id else False,
                }
            )

            # Apply onchange logic to populate pricing fields
            new_concept._onchange_product_id()

            # Retrieve full record data
            # concept_data = request.env["ike.event.supplier.product"].search(
            #     [
            #         ("id", "=", new_concept.id),
            #     ],
            #     limit=1,
            # )
            # concept_data._onchange_product_id()

            _logger.info(
                f"Created concept {new_concept.id} for event {event_id}, supplier {supplier_id}, product {product_id}"
            )

            return {
                "success": True,
                "concept_id": new_concept.id,
                "message": "Concept created successfully",
            }

        except Exception as e:
            _logger.error(f"Error creating concept: {str(e)}")
            return {"success": False, "error": str(e)}

    @http.route(
        "/provider/portal/supplier/request_authorization", type="json", auth="user"
    )
    def request_authorization(self, event_supplier_id):
        supplier = request.env["ike.event.supplier"].browse(event_supplier_id)
        supplier.action_request_authorization()
        return {"success": True}

    @http.route("/fleet/vehicle/safe/<int:vehicle_id>", type="json", auth="user")
    def get_vehicle_safe(self, vehicle_id):
        """Returns EXACTLY the same format as searchRead with name instead of display_name"""
        try:
            # Get vehicle with sudo
            vehicle = request.env["fleet.vehicle"].sudo().browse(vehicle_id)
            if not vehicle.exists():
                return []
            # Get all fields using search_read
            vehicle_data = (
                request.env["fleet.vehicle"]
                .sudo()
                .search_read(
                    [("id", "=", vehicle_id)],
                    [
                        "name",
                        "x_partner_id",
                        "x_vehicle_type",
                        "license_plate",
                        "x_vehicles_axes",
                        "x_federal_license_plates",
                        "x_manages_tire_conditioning",
                        "x_product_category_id",
                        # "x_product_id", # ToDo delete after test change to x_subservice_ids
                        "x_subservice_ids",
                        "x_vehicle_service_state",
                        "x_maneuvers",
                        "x_accessories",
                        "driver_id",
                        "x_center_id",
                        "x_manages_tire_conditioning",
                    ],
                )
            )
            if not vehicle_data:
                return []
            result = vehicle_data[0]
            # ToDo delete after test change to x_subservice_ids
            # # Process x_product_id to return [id, name] instead of [id, display_name]
            # if result.get("x_product_id"):
            #     product_id = result["x_product_id"][0]  # Get the ID
            #     product = request.env["product.product"].sudo().browse(product_id)
            #     if product.exists():
            #         result["x_product_id"] = [product.id, product.name]
            # # Process x_accessories to return [[id, name], ...] instead of [[id, display_name], ...]
            # # if result.get('x_accessories'):
            # #     accessory_ids = [acc[0] for acc in result['x_accessories']]  # Extract IDs
            # #     accessories = request.env['product.product'].sudo().browse(accessory_ids)
            # #     # Create new list with [id, name] format
            # #     result['x_accessories'] = [[acc.id, acc.name, acc.display_name] for acc in accessories if acc.exists()]

            if result.get("x_subservice_ids"):
                subservice_ids = result["x_subservice_ids"]
                subservices = (
                    request.env["product.product"].sudo().browse(subservice_ids)
                )
                result["x_subservice_ids"] = [
                    [s.id, s.name] for s in subservices if s.exists()
                ]
            else:
                result["x_subservice_ids"] = []

            return [result]
        except Exception as e:
            _logger.error(f"Error getting vehicle {vehicle_id}: {str(e)}")
            return []
