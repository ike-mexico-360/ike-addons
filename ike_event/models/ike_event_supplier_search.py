# -*- coding: utf-8 -*-

import base64
import json
import logging
import math
import requests

from datetime import timedelta

from odoo import models, fields, Command, _
from odoo.exceptions import UserError, ValidationError

from .other_models.ike_event_batcher import event_batcher

_logger = logging.getLogger(__name__)


class IkeEvent_Search(models.Model):
    _inherit = 'ike.event'

    supplier_number = fields.Integer(default=1, copy=False)
    supplier_search_date = fields.Datetime(readonly=True, copy=False)
    supplier_search_type = fields.Selection([
        ('electronic', 'Electronic'),
        ('publication', 'Publication'),
        ('manual', 'Manual'),
        ('manual_manual', 'Manual Added'),
    ], default='electronic', string="Search Type (Supplier)", copy=False)
    supplier_search_priority = fields.Integer()
    supplier_search_number = fields.Integer(string='Search Number (Supplier)', default=0, copy=False)
    base_supplier_number = fields.Integer(default=1, copy=False)
    use_external_locations = fields.Boolean(default=True)

    # === SUPPLIER SEARCH ACTIONS === #
    def action_search_electronic_suppliers(self):
        """ Action View Button to search suppliers: Electronic. """
        self.ensure_one()
        self._search_suppliers('electronic')

    def action_search_publication_suppliers_3(self,):
        """ Action View Button to search suppliers: Publication Priority 3. """
        self.ensure_one()
        self._search_suppliers('publication', '3')

    def action_search_publication_suppliers_2(self):
        """ Action View Button to search suppliers: Publication Priority 2. """
        self.ensure_one()
        self._search_suppliers('publication', '2')

    def action_search_publication_suppliers_1(self):
        """ Action View Button to search suppliers: Publication Priority 1. """
        self.ensure_one()
        self._search_suppliers('publication', '1')

    def action_search_publication_suppliers_0(self):
        """ Action View Button to search suppliers: Publication Priority 0. """
        self.ensure_one()
        self._search_suppliers('publication', '0')

    def action_search_manual_suppliers(self):
        """ Action View Button to search suppliers: Manual. """
        self.ensure_one()
        self._search_suppliers('manual')

    def _search_suppliers(self, assignation_type, priority=None):
        """ Function to assign """
        self.ensure_one()
        locked_record_ids = self._with_locked_records()
        if not locked_record_ids:
            return

        # Algorithm
        service_suppliers, max_suppliers, limit_max_distance_km = self._search_suppliers_algorithm(assignation_type, priority)

        if len(service_suppliers):
            # Supplier products with costs
            current_authorization_ids = self.authorization_ids.filtered(lambda x: x.supplier_number <= self.supplier_number)
            # Max Distance by Supplier
            supplier_max_distances = {}
            max_cost_distance_km: float = 0.0
            for supplier in service_suppliers:
                if supplier['cost_distance'] > max_cost_distance_km:
                    max_cost_distance_km = supplier['cost_distance']
                if supplier['cost_distance'] > supplier_max_distances.get(supplier['supplier_id'], 0):
                    supplier_max_distances[supplier['supplier_id']] = supplier['cost_distance']

            # Covered Amount, from table
            self._set_covered_amount(max_cost_distance_km + (self.destination_distance or 0))

            # Supplies
            for supplier in service_suppliers:
                supplier_link_id = self.service_supplier_link_ids.filtered(
                    lambda x:
                        x.supplier_id.id == supplier['supplier_id']
                        and x.supplier_number == self.supplier_number,
                )

                # Supplier Link
                if not supplier_link_id:
                    # User amount paid lines Vertical Dragging
                    current_user_payment_line_ids = (
                        self.service_supplier_ids.filtered(
                            lambda x: x.user_payment_lines_count > 0 and x.search_number < self.supplier_search_number
                        )
                        .sorted(
                            lambda x: (
                                x.supplier_id.id != supplier['supplier_id'],
                                -x.search_number,
                            )
                        )[:1]
                        .supplier_link_id.user_payment_line_ids
                    )
                    current_user_payment_lines = [
                        Command.create(
                            {
                                'payment_type': x.payment_type,
                                'payment_datetime': x.payment_datetime,
                                'amount': x.amount,
                            }
                        )
                        for x in current_user_payment_line_ids
                    ]
                    # Distance km
                    total_distance_km = supplier_max_distances.get(supplier['supplier_id'], 0)
                    if supplier['negotiation_type'] == 'base_base':
                        total_distance_km = (total_distance_km + (self.destination_distance or 0)) * 2.0
                    elif supplier['negotiation_type'] in ['base_destination', 'vehicle_destination']:
                        total_distance_km += (self.destination_distance or 0)
                    elif supplier['negotiation_type'] == 'origin_destination':
                        total_distance_km = (self.destination_distance or 0)
                    elif supplier['negotiation_type'] == 'base_concept':
                        total_distance_km = 0.0
                    else:
                        total_distance_km = 0.0
                    total_distance_km = int(-(-total_distance_km // 1))  # To integer

                    # Add link
                    supplier_products_data = self.get_supplier_products_data(
                        supplier['supplier_center_id'],
                        supplier['supplier_id'],
                        total_distance_km)
                    for product_data in supplier_products_data:
                        product_data[2]['supplier_number'] = self.supplier_number

                    supplier_link_id = self.env['ike.event.supplier.link'].with_context(from_internal=True).create({
                        'event_id': self.id,
                        'supplier_id': supplier['supplier_id'],
                        'supplier_number': self.supplier_number,
                        'supplier_product_ids': supplier_products_data,
                        'user_payment_line_ids': current_user_payment_lines,
                    })
                    # Manual Notification
                    supplier_link_id.manual_notification = (
                        supplier_link_id.supplier_id.x_has_external_notification or supplier_link_id.supplier_id.x_has_portal
                    )
                    # Set Authorization Data
                    authorized = (self.previous_amount + supplier_link_id.estimated_cost) <= self.authorized_amount
                    for product_id in supplier_link_id.supplier_product_ids:
                        if authorized and product_id.covered and product_id.subtotal > 0:
                            product_id.authorization_pending = False
                            if current_authorization_ids:
                                product_id.authorization_ids = [Command.create({
                                    'event_authorization_id': current_authorization_ids[0].id,
                                    'quantity': product_id.quantity,
                                    'unit_price': product_id.unit_price,
                                })]
                        else:
                            product_id.authorization_pending = True

                    # Products cost by km
                    products_cost_by_km = supplier_link_id.supplier_product_ids.filtered(
                        lambda x: x.product_id.x_cost_by_km and not x.parent_product_id
                    )
                    if len(products_cost_by_km):
                        products_cost_by_km.with_context(ignore_authorization=True).quantity = total_distance_km

                # Zero Cost
                has_zero = any(
                    x.product_id and x.base_unit_price == 0
                    for x in supplier_link_id.supplier_product_ids
                )
                if has_zero:
                    supplier['ignore'] = True

                # Set link totals
                supplier['supplier_link_id'] = supplier_link_id.id
                supplier['estimated_cost'] = supplier_link_id.amount_concept_total

                # Electronic Search ignore
                if assignation_type == 'electronic' and supplier['estimated_cost'] > self.authorized_amount:
                    supplier['ignore'] = True

            # Filter and Sort Suppliers by
            service_suppliers = sorted(
                [item for item in service_suppliers if not item.get('ignore')],
                key=lambda x: (x['estimated_duration'], x['estimated_cost'], -int(x['priority'] or 0))
            )
            # Filter manual: first of each supplier
            if assignation_type == 'manual':
                seen = set()
                service_suppliers = [
                    x for x in service_suppliers
                    if not (x["supplier_id"] in seen or seen.add(x["supplier_id"]))
                ]
            service_suppliers = service_suppliers[:max_suppliers]

            # Set Google Route
            if assignation_type == 'electronic':
                for supplier in service_suppliers:
                    # if supplier['latitude'] and supplier['longitude']:
                    destination_distance_m, destination_duration_s, destination_route = (
                        self.get_destination_route(
                            supplier['latitude'],
                            supplier['longitude'],
                            self.location_latitude,
                            self.location_longitude,
                        )
                    )
                    if destination_route:
                        distance_km = (destination_distance_m or supplier['estimated_distance']) / 1000.00
                        duration_m = (destination_duration_s or supplier['estimated_duration']) / 60.00
                        supplier['route'] = destination_route
                        supplier['real_distance'] = distance_km
                        supplier['real_duration'] = duration_m
                        if not supplier['estimated_distance'] or not supplier.get('osrm'):
                            supplier['estimated_distance'] = distance_km
                            supplier['estimated_duration'] = duration_m

        # Search Number
        search_number = 0
        line_id = self.env['ike.event.supplier'].search_read([
            ('event_id', '=', self.id)
        ], ['search_number'], limit=1, order='search_number desc')
        if line_id:
            search_number = line_id[0].get('search_number', 0)
        self.supplier_search_number = search_number + 1
        self.supplier_search_type = assignation_type

        # Save Supplier Lines
        self._process_suppliers_data(service_suppliers, assignation_type, priority)

        # Check Lines
        line_ids = self.service_supplier_ids.filtered(
            lambda x:
                x.search_number == self.supplier_search_number
                and not x.display_type
        )
        if len(line_ids):
            if not self.authorization_required:
                # Automatic notification
                if assignation_type == 'electronic':
                    line_ids[0].action_notify()
                elif assignation_type == 'publication':
                    line_ids.action_notify()
        else:
            # Automatic next assignation_type
            if assignation_type == 'electronic':
                self._search_suppliers('publication', '3')
            elif assignation_type == 'publication':
                priority = int(priority or 0)
                if priority > 1:
                    next_priority = str(priority - 1)
                    self._search_suppliers('publication', next_priority)
                else:
                    self._search_suppliers('manual')

        self.broadcastSuppliersNotifications()

    def action_search_suppliers_test(self):
        priority = self.supplier_search_priority
        if priority == 0:
            priority = None
        content = self._search_suppliers_test(self.supplier_search_type, priority)
        attachment = self.env['ir.attachment'].create({
            'name': f'{self.name}.txt',
            'type': 'binary',
            'datas': base64.b64encode(content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'text/plain',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _search_suppliers_test(self, assignation_type, priority=None):
        self.ensure_one()
        content = f"SEARCH: {assignation_type} {priority}\n"
        if priority:
            priority = str(priority)

        # Algorithm
        service_suppliers, max_suppliers, limit_max_distance_km = self._search_suppliers_algorithm(assignation_type, priority)

        if len(service_suppliers):
            # Max Distance by Supplier
            supplier_max_distances = {}
            max_cost_distance_km: float = 0.0
            for supplier in service_suppliers:
                if supplier['cost_distance'] > max_cost_distance_km:
                    max_cost_distance_km = supplier['cost_distance']
                if supplier['cost_distance'] > supplier_max_distances.get(supplier['supplier_id'], 0):
                    supplier_max_distances[supplier['supplier_id']] = supplier['cost_distance']

            supplier_products = {}
            for supplier in service_suppliers:
                content += f"supplier_id: {supplier['supplier_id']}, supplier_center_id: {supplier['supplier_center_id']}"
                content += f", vehicle_id: {supplier['truck_id']} ({supplier['latitude']}, {supplier['longitude']})"
                content += f", negotiation_type: {supplier['negotiation_type']}"
                content += f", estimated_distance: {supplier['estimated_distance']}"
                content += f", estimated_duration: {supplier['estimated_duration']}"
                content += f", cost_distance: {supplier['cost_distance']}"
                content += "\n"
                if supplier['supplier_id'] in supplier_products:
                    continue
                # Distance km
                total_distance_km = supplier_max_distances.get(supplier['supplier_id'], 0)
                if supplier['negotiation_type'] == 'base_base':
                    total_distance_km = (total_distance_km + (self.destination_distance or 0)) * 2.0
                elif supplier['negotiation_type'] in ['base_destination', 'vehicle_destination']:
                    total_distance_km += (self.destination_distance or 0)
                elif supplier['negotiation_type'] == 'origin_destination':
                    total_distance_km = (self.destination_distance or 0)
                elif supplier['negotiation_type'] == 'base_concept':
                    total_distance_km = 0.0
                else:
                    total_distance_km = 0.0
                total_distance_km = int(-(-total_distance_km // 1))  # To integer

                # Products
                supplier_products[supplier['supplier_id']], sql = self.get_supplier_products_data_test(
                    supplier['supplier_center_id'],
                    supplier['supplier_id'],
                    total_distance_km)

                content += "QUERY\n" + sql + "\n"

            content += "\n"
            content += "PRODUCTS\n"
            for key, value in supplier_products.items():
                content += f"supplier_id: {key}: "
                content += "\n"
                content += json.dumps(value, indent=4, ensure_ascii=False)
                content += "\n"

        return content

    # === ALGORITHM === #
    def _search_suppliers_algorithm(self, assignation_type, priority=None) -> tuple[list[dict], int, float]:
        """ Algorithm """
        self.ensure_one()
        service_suppliers = []

        # * LOGGER 0: Start
        _logger.info(f"IKE EVENT - DEBUG - 0: {assignation_type} {str(priority)}")

        # Global Variables
        maneuver_id = self.env.ref('ike_event.ike_product_tag_maneuvers').id
        # To Filter supplier geographical areas
        sequence_conf = 1
        assignation_type_conf = ''
        if assignation_type == 'electronic':
            sequence_conf = 1
            assignation_type_conf = ' AND su.x_is_electronic'
        elif assignation_type == 'publication':
            sequence_conf = 2
            assignation_type_conf = ' AND su.x_is_electronic'
        elif assignation_type == 'manual':
            sequence_conf = 3
            assignation_type_conf = ' AND su.x_is_manual'

        # Searching Configuration
        timer_duration_s, max_suppliers, max_arrived_time_m, max_radius_km = self._get_search_configuration(sequence_conf)

        # Event variables
        account_id = self.user_membership_id.membership_plan_id.account_id.id
        if not account_id:
            raise UserError(_('No account was assigned to the membership.'))

        zip_code = self.location_zip_code
        latitude = self.location_latitude
        longitude = self.location_longitude
        if not latitude or not longitude:
            raise UserError(_('No latitude/longitude was assigned to the location.'))

        # Event models variables
        municipality, vehicle_category_id = self._get_event_service_variables()
        service_vehicle_type_ids, service_accessory_ids = self._get_event_sub_service_variables()

        # * LOGGER 1: Event Variables
        _logger.info(
            f"IKE EVENT - DEBUG - 1: {account_id}, {zip_code}, {latitude}, {longitude}, {str(service_vehicle_type_ids)}"
        )

        # Get Municipalities
        municipalities_data = self._get_municipalities(zip_code)
        if municipality:
            municipalities_data.append({'id': municipality.id, 'name': municipality.name})
        if not len(municipalities_data):
            return [], max_suppliers, max_radius_km

        # * LOGGER 2: Municipalities
        municipalities_text = ','.join([f'{x['id']}.{x['name']}' for x in municipalities_data])
        _logger.info(f"IKE EVENT - DEBUG - 2: {municipalities_text}")

        # Get Supplier Centers
        supplier_centers_data = self._get_supplier_centers(assignation_type_conf, municipalities_data, priority)
        # Get Supplier Centers, Priority filter
        supplier_centers_data = [x for x in supplier_centers_data if not priority or x['priority'] == priority]
        if not len(supplier_centers_data):
            return [], 0, 0

        # No duplicates suppliers 1
        suppliers = [x['supplier_id'] for x in supplier_centers_data]
        suppliers = list(set(suppliers))

        # Validate account Included/Excluded
        supplier_accounts_data = self.env['res.partner'].search_read([
            ('id', 'in', suppliers)
        ], ['x_special_account_ids', 'x_exclusive_account_ids'])
        for supplier in supplier_centers_data:
            account = next((x for x in supplier_accounts_data if x['id'] == supplier['supplier_id']), {})
            supplier['x_special_account_ids'] = account.get('x_special_account_ids')
            supplier['x_exclusive_account_ids'] = account.get('x_exclusive_account_ids')
        # Included
        included_supplier_centers_data = [
            x for x in supplier_centers_data
            if x['x_special_account_ids'] and account_id in x['x_special_account_ids']
        ]
        if len(included_supplier_centers_data):
            supplier_centers_data = included_supplier_centers_data
        # Excluded
        supplier_centers_data = [
            x for x in supplier_centers_data
            if not x['x_is_exclusive_accounts'] or account_id not in x['x_exclusive_account_ids']
        ]

        # No duplicates suppliers 2
        supplier_centers = [x['supplier_center_id'] for x in supplier_centers_data]
        supplier_centers = list(set(supplier_centers))

        # * LOGGER 3: Suppliers and Supplier Centers
        suppliers_text = ','.join(map(str, suppliers))
        supplier_centers_text = ','.join(map(str, supplier_centers))
        _logger.info(f"IKE EVENT - DEBUG - 3: {suppliers_text} - {supplier_centers_text}")

        # Supplier Lines Result
        service_suppliers = []

        # Subservices that requires a service a vehicle
        if self.sub_service_ref in ('town_truck', 'tire_change', 'fuel_supply', 'other_fluid', 'battery_jump'):
            # Previous Service Vehicles Excluded
            previous_trucks = []
            if assignation_type == 'publication':
                previous_trucks = self.service_supplier_ids.filtered(
                    lambda x: x.assignation_type == 'electronic' and x.search_number <= self.supplier_search_number
                ).mapped('truck_id.id')

            # Get Service Vehicles
            vehicles_domain = [
                ('id', 'not in', previous_trucks),
                ('disabled', '=', False),
                ('x_partner_id', 'in', suppliers),
                ('x_center_id', 'in', supplier_centers),
                ('driver_id', '!=', False),
                ('x_vehicle_type', 'in', service_vehicle_type_ids),
                ('x_vehicle_service_state', '=', 'available'),
            ]

            # Federal Plates
            if self.requires_federal_plates:
                vehicles_domain.append(
                    ('x_federal_license_plates', '=', True),
                )
            # Accessories
            if len(service_accessory_ids):
                vehicles_domain.append(('x_maneuvers', '=', True))
                for accessory_id in service_accessory_ids:
                    vehicles_domain.append(('x_accessories', 'in', [accessory_id]))
            # Maneuvers
            product_tag_ids = self.service_product_ids.mapped('product_id.product_tag_ids.id')
            if maneuver_id in product_tag_ids:
                vehicles_domain.append(('x_maneuvers', '=', True))

            # * LOGGER 4: Vehicles Domain
            _logger.info("IKE EVENT - DEBUG - 4: %s", vehicles_domain)

            # Search Vehicles
            if assignation_type == 'electronic':
                service_vehicles_data = self._get_electronic_vehicles_data(vehicles_domain, max_radius_km)
            else:
                service_vehicles_data = self._get_vehicles_data(vehicles_domain, max_radius_km)

            # * LOGGER 5: Service Vehicles
            vehicles_text = ", ".join([
                f"{x['id']}.{x['license_plate']} ({str(x['estimated_distance'])}, {str(x['estimated_duration'])})"
                for x in service_vehicles_data
            ])
            _logger.info(f"IKE EVENT - DEBUG - 5: ({str(max_radius_km)}, {str(max_arrived_time_m)}), {vehicles_text}")

            # Filter vehicles by negotiation type rules
            service_vehicles_data = [
                x for x in service_vehicles_data
                if not x['no_distance']
                and (
                    x['estimated_distance'] > 0
                    and x['estimated_distance'] <= (max_radius_km * 1.5)
                    and x['estimated_duration'] <= (max_arrived_time_m * 1.5)
                )
                or x.get('bypass', False)
            ]

            # Set Priority
            supplier_center_data = {'supplier_center_id': 0}
            for vehicle in service_vehicles_data:
                if supplier_center_data['supplier_center_id'] != vehicle['supplier_center_id']:
                    supplier_center_data = next(
                        (x for x in supplier_centers_data if x['supplier_center_id'] == vehicle['supplier_center_id']),
                        {}
                    )
                vehicle['priority'] = supplier_center_data['priority']

            # SERVICE VEHICLES RESULT
            service_vehicles_len = len(service_vehicles_data)
            for i in range(0, service_vehicles_len):
                vehicle = service_vehicles_data[i]
                service_suppliers.append({
                    'event_id': self.id,
                    'assignation_type': assignation_type,
                    'name': f"{_('License Plate')}: {vehicle['license_plate']}",
                    'supplier_id': vehicle['supplier_id'],
                    'supplier_center_id': vehicle['supplier_center_id'],
                    'state': 'available',
                    'priority': vehicle['priority'],
                    'negotiation_type': vehicle['negotiation_type'],
                    'estimated_distance': vehicle['estimated_distance'],
                    'estimated_duration': vehicle['estimated_duration'],
                    'cost_distance': vehicle['cost_distance'],
                    'osrm': vehicle.get('osrm'),
                    'timer_duration': timer_duration_s,
                    'is_manual': bool(assignation_type == 'manual'),
                    'truck_id': vehicle['id'],
                    'assigned': vehicle['driver_name'],
                    'latitude': vehicle['latitude'],
                    'longitude': vehicle['longitude'],
                    'bypass': vehicle.get('bypass', False),
                })

        # * LOGGER 6: Service suppliers
        _logger.info(f"IKE EVENT - DEBUG - 6: {service_suppliers}")
        return service_suppliers, max_suppliers, max_radius_km

    def _get_search_configuration(self, sequence_conf):
        timer_duration_s = 40
        max_suppliers = 5
        max_arrived_time_m = 35
        max_radius_km = 3.0
        configuration = self.env['ike.event.supplier.assignment.type'].search_read([
            ('sequence', '=', sequence_conf)
        ], ['id', 'wait_time', 'max_suppliers', 'by_priority', 'arrival_duration', 'geofence_radius'])
        if len(configuration):
            timer_duration_s = configuration[0]['wait_time'] or 100000  # In Seconds
            max_suppliers = configuration[0]['max_suppliers'] or 20
            max_arrived_time_m = configuration[0]['arrival_duration']  # In Minutes
            max_radius_km = configuration[0]['geofence_radius'] or 15.0  # In Kilometers

        return timer_duration_s, max_suppliers, max_arrived_time_m, max_radius_km

    def _get_event_sub_service_variables(self) -> tuple[list[int], list[int]]:
        sub_res_id = self.env[self.sub_service_res_model].browse(self.sub_service_res_id)
        service_vehicle_type_ids = []
        service_accessory_ids = []
        if self.sub_service_ref in ['town_truck', 'tire_change', 'fuel_supply', 'other_fluid', 'battery_jump']:
            service_vehicle_type_ids = sub_res_id.service_vehicle_type_ids.ids  # type: ignore
            service_accessory_ids = sub_res_id.service_accessory_ids.ids  # type: ignore

        return service_vehicle_type_ids, service_accessory_ids

    def _get_event_service_variables(self):
        res_id = self.env[self.service_res_model].browse(self.service_res_id)
        vehicle_category_id = res_id.vehicle_category_id.id  # type: ignore
        municipality = res_id.municipality_id  # type: ignore
        return municipality, vehicle_category_id

    def _get_municipalities(self, zip_code):
        self._cr.execute("""
            SELECT distinct
                mc.municipality_id as id
                ,m.name
            FROM custom_state_municipality_code mc
            INNER JOIN custom_state_municipality m on m.id = mc.municipality_id
            WHERE mc.zip_code = %(zip_code)s
                AND mc.active AND NOT mc.disabled;
        """, {
            'zip_code': zip_code,
        })
        municipalities_data = self._cr.dictfetchall()

        return municipalities_data

    def _get_supplier_centers(self, assignation_type_conf: str, municipalities_data: list, priority=None):
        query = """
            SELECT DISTINCT
                ga.partner_id as supplier_center_id
                ,ga.parent_id as supplier_id
                ,su.x_negotiation_type
                ,gap.priority
                ,su.x_is_special_accounts
                ,su.x_is_exclusive_accounts
                ,gap.product_id
            FROM custom_geographical_area ga
            INNER JOIN res_partner su on su.id = ga.parent_id
            INNER JOIN custom_geographical_area_product_rel gap on gap.geographical_area_id = ga.id
            WHERE
                ga.municipality_id IN %(municipality_ids)s
                AND NOT ga.disabled AND ga.active
                AND NOT su.disabled AND su.active
                AND gap.product_id = %(subservice_id)s
        """

        query += assignation_type_conf

        params = {
            "municipality_ids": tuple(x["id"] for x in municipalities_data),
            "subservice_id": self.sub_service_id.id,
        }

        if priority is not None:
            query += " AND gap.priority = %(priority)s::text"
            params["priority"] = str(priority)
        query += " ORDER BY ga.partner_id desc"

        self._cr.execute(query, params)
        return self._cr.dictfetchall()

    def _get_electronic_vehicles_data(self, vehicles_domain, max_radius_km):
        service_vehicle_ids = self.env['fleet.vehicle'].search(vehicles_domain, order='x_center_id')

        service_vehicles_data = [{
            'id': rec.id,
            'ref': rec.x_vehicle_ref,
            'driver_id': rec.driver_id.id,
            'driver_name': rec.driver_id.name,
            'license_plate': rec.license_plate,
            'vehicle_type': rec.vehicle_type,
            'supplier_id': rec.x_partner_id.id,
            'supplier_center_id': rec.x_center_id.id,
            'latitude': rec.x_latitude,
            'longitude': rec.x_longitude,
            'negotiation_type': 'vehicle_destination',  # Always
            'center_latitude': rec.x_center_id.partner_latitude,
            'center_longitude': rec.x_center_id.partner_longitude,
            'estimated_distance': 0,
            'estimated_duration': 0,
            'cost_distance': 0,
            'bypass': False,
            'no_distance': False,  # ToPop
        } for rec in service_vehicle_ids]

        origin_latitude = float(self.location_latitude)
        origin_longitude = float(self.location_longitude)

        vehicles_osrm_data = []
        if self.use_external_locations:
            vehicles_osrm_data = self._get_external_vehicles_location(
                origin_latitude,
                origin_longitude,
                vehicle_refs=[x['ref'] for x in service_vehicles_data],
                radius_m=float(max_radius_km * 1000),
                max_distance_m=float(max_radius_km * 1.4 * 1000),
            )
        for vehicle in service_vehicles_data:
            data = None
            if len(vehicles_osrm_data):
                data = next(
                    (x for x in vehicles_osrm_data if x['vehicle_ref'] == vehicle['ref']),
                    None
                )
            if data:
                vehicle['latitude'] = data.get('lat', None)
                vehicle['longitude'] = data.get('lng', None)
                vehicle['estimated_distance'] = data.get('distance_m', 0) / 1000
                vehicle['estimated_duration'] = data.get('duration_s', 0) / 60
                vehicle['osrm'] = True
            elif not self.use_external_locations:
                if not vehicle['latitude'] or not vehicle['longitude']:
                    continue
                osrm_distance = self.get_osrm_distance(
                    vehicle['latitude'], vehicle['longitude'],
                    origin_latitude, origin_longitude
                )
                vehicle.update(osrm_distance)
            else:
                vehicle['no_distance'] = True
            vehicle['cost_distance'] = vehicle['estimated_distance']

        return service_vehicles_data

    def _get_vehicles_data(self, vehicles_domain, max_radius_km):
        service_vehicle_ids = self.env['fleet.vehicle'].search(vehicles_domain, order='x_center_id')

        service_vehicles_data = [{
            'id': rec.id,
            'ref': rec.x_vehicle_ref,
            'driver_id': rec.driver_id.id,
            'driver_name': rec.driver_id.name,
            'license_plate': rec.license_plate,
            'vehicle_type': rec.vehicle_type,
            'supplier_id': rec.x_partner_id.id,
            'supplier_center_id': rec.x_center_id.id,
            'latitude': rec.x_latitude,
            'longitude': rec.x_longitude,
            'negotiation_type': rec.x_partner_id.x_negotiation_type or 'base_destination',
            'center_latitude': rec.x_center_id.partner_latitude,
            'center_longitude': rec.x_center_id.partner_longitude,
            'estimated_distance': 0,
            'estimated_duration': 0,
            'cost_distance': 0,
            'no_distance': False,  # It was not possible to obtain distance
            'bypass': False,  # At least one per supplier
        } for rec in service_vehicle_ids]

        base_origin_distances = {}
        vehicle_refs = []

        origin_latitude = float(self.location_latitude)
        origin_longitude = float(self.location_longitude)

        no_distance_suppliers = set()

        for vehicle in service_vehicles_data:
            supplier_id = vehicle['supplier_id']
            if supplier_id in no_distance_suppliers:
                vehicle['no_distance']
                continue
            negotiation_type = vehicle['negotiation_type']
            vehicle_latitude = float(vehicle['latitude'])
            vehicle_longitude = float(vehicle['longitude'])
            supplier_center_id = vehicle['supplier_center_id']
            center_latitude = float(vehicle['center_latitude'])
            center_longitude = float(vehicle['center_longitude'])

            if negotiation_type in ['base_base', 'base_destination', 'base_concept'] or not negotiation_type:
                if center_latitude and center_longitude:
                    if supplier_center_id not in base_origin_distances:
                        base_origin_distances[supplier_center_id] = self.get_osrm_distance(
                            center_latitude, center_longitude,
                            origin_latitude, origin_longitude
                        )
                    vehicle.update(base_origin_distances[supplier_center_id])
                if negotiation_type in ['base_base', 'base_concept']:
                    if base_origin_distances.get(supplier_center_id, False):
                        # Set Center lat/lng and distance/duration
                        vehicle.update(base_origin_distances[supplier_center_id])
                        vehicle['latitude'] = center_latitude
                        vehicle['longitude'] = center_longitude
                        if negotiation_type == 'base_concept':
                            vehicle['cost_distance'] = 0.0
                    else:
                        vehicle['no_distance']
                        no_distance_suppliers.add(supplier_id)
                elif negotiation_type == 'base_destination':
                    if self.use_external_locations:
                        vehicle_refs.append(vehicle['ref'])
                        vehicle['negotiation_type'] = 'vehicle_destination'
                    else:
                        # Debug/Local Only
                        if vehicle_latitude and vehicle_latitude:
                            osrm_distance = self.get_osrm_distance(
                                vehicle_latitude, vehicle_longitude,
                                origin_latitude, origin_longitude
                            )
                            vehicle.update(osrm_distance)
                        elif base_origin_distances.get(supplier_center_id):
                            vehicle.update(base_origin_distances[supplier_center_id])
                            vehicle['latitude'] = center_latitude
                            vehicle['longitude'] = center_longitude
                        else:
                            vehicle['no_distance'] = True
                        vehicle['osrm'] = True
            elif negotiation_type == 'origin_destination':
                vehicle['latitude'] = origin_latitude
                vehicle['longitude'] = origin_longitude
                vehicle['estimated_distance'] = 0
                vehicle['estimated_duration'] = 0
                vehicle['cost_distance'] = 0
                vehicle['bypass'] = True
            else:
                pass

        if len(vehicle_refs):
            vehicles_osrm_data = self._get_external_vehicles_location(
                origin_latitude,
                origin_longitude,
                vehicle_refs=[str(x) for x in vehicle_refs],
                radius_m=float(max_radius_km * 1000),
                max_distance_m=float(max_radius_km * 1.4 * 1000),
            )

            for vehicle in service_vehicles_data:
                if vehicle['negotiation_type'] == 'vehicle_destination':
                    supplier_id = vehicle['supplier_id']
                    vehicle_latitude = float(vehicle['latitude'])
                    vehicle_longitude = float(vehicle['longitude'])
                    supplier_center_id = vehicle['supplier_center_id']
                    center_latitude = float(vehicle['center_latitude'])
                    center_longitude = float(vehicle['center_longitude'])

                    data = next(
                        (x for x in vehicles_osrm_data if x['vehicle_ref'] == vehicle['ref']),
                        None
                    )
                    if data:
                        vehicle['latitude'] = data.get('lat', None)
                        vehicle['longitude'] = data.get('lng', None)
                        vehicle['estimated_distance'] = data.get('distance_m', 0) / 1000
                        vehicle['estimated_duration'] = data.get('duration_s', 0) / 60
                        vehicle['cost_distance'] = data.get('duration_s', 0) / 60
                        vehicle['osrm'] = True
                    elif base_origin_distances.get(supplier_center_id):
                        # Set Center lat/lng and distance/duration
                        vehicle.update(base_origin_distances[supplier_center_id])
                        vehicle['negotiation_type'] = 'base_destination'
                        vehicle['latitude'] = center_latitude
                        vehicle['longitude'] = center_longitude
                    else:
                        vehicle['no_distance'] = True

        # First one of each combination supplier/supplier_center
        seen = set()

        service_vehicles_data = sorted(
            [item for item in service_vehicles_data],
            key=lambda x: (x['estimated_duration'])
        )
        service_vehicles_data = [
            x for x in service_vehicles_data
            if not (
                (x["supplier_id"], x["supplier_center_id"]) in seen
                or seen.add((x["supplier_id"], x["supplier_center_id"]))
            )
        ]

        return service_vehicles_data

    # === PRODUCTS METHODS === #
    def get_supplier_products_matrix_line_ids(
        self,
        supplier_center_id: int,
        product_ids: list[int],
        status_ref: str,
    ):
        """ Get Matrix Lines ids by Query """
        query, params = self._get_supplier_products_matrix_query(supplier_center_id, product_ids, status_ref)
        self.env.cr.execute(query, params)
        return self.env.cr.dictfetchall()

    def _get_supplier_products_matrix_query(
        self,
        supplier_center_id: int,
        product_ids: list[int],
        status_ref: str,
    ):
        # Variables
        municipality, vehicle_category_id = self._get_event_service_variables()

        if not municipality:
            return []

        sub_service_id: int = self.sub_service_id.id
        event_type_id: int = self.event_type_id.id
        vehicle_category_id: int = vehicle_category_id
        state_id: int = municipality.state_id.id
        municipality_id: int = municipality.id
        account_id: int = self.user_membership_id.membership_plan_id.account_id.id
        event_date = self.event_date + timedelta(hours=6)  # ToDo: use time zone from geographical area (new one)
        event_time = event_date.hour + event_date.minute / 60 + event_date.second / 3600
        event_date = event_date.date()
        is_holiday = self.env['custom.holidays'].search_count([('date', '=', event_date)], limit=1)

        params = {
            "event_time": event_time,
            "is_holiday": is_holiday,
            "supplier_center_id": supplier_center_id,
            "sub_service_id": sub_service_id,
            "event_type_id": event_type_id,
            "vehicle_category_id": vehicle_category_id,
            "status_ref": status_ref,
            "state_id": state_id,
            "municipality_id": municipality_id,
            "account_id": account_id,
            "event_date": event_date,
            "product_ids": product_ids,
        }

        query = """
            WITH matrix AS (
                SELECT
                    m.id
                    ,m.concept_id AS product_id
                    ,m.state_id
                    ,m.geographical_area_id AS municipality_id
                    ,m.account_id
                    ,m.date_init
                    ,m.date_end
                    ,COALESCE(sc.start_time, 0) AS start_time
                    ,COALESCE(sc.end_time, 24) AS end_time
                    ,CASE WHEN %(event_time)s BETWEEN start_time AND end_time THEN 1 ELSE 0 END AS in_time
                    ,m.holiday_date_applies::int = %(is_holiday)s as holiday_applies
                    ,m.holiday_date_applies
                    ,st.ref AS supplier_status_ref
                    ,svc.vehicle_category_id
                FROM custom_supplier_cost_matrix_line m
                INNER JOIN custom_supplier_types_statuses st ON st.id = m.supplier_status_id
                INNER JOIN custom_subservice_specification_vehicle_category_rel svc ON
                    svc.subservice_specification_id = m.subservice_specification_id
                LEFT JOIN vacation_schedule_cost_product_rel_id scr ON scr.custom_supplier_cost_product_id = m.id
                LEFT JOIN custom_supplier_cost_product_schedule sc ON scr.custom_supplier_cost_product_schedule_id = sc.id
                WHERE m.active AND NOT m.disabled
                    AND m.supplier_center_id = %(supplier_center_id)s
                    AND m.subservice_id = %(sub_service_id)s
                    AND m.type_event_id = %(event_type_id)s
                    AND svc.vehicle_category_id = %(vehicle_category_id)s
                    AND st.ref = %(status_ref)s
            )
            SELECT
                p.id AS product_id,
                m.id AS matrix_line_id
            FROM product_product p
            JOIN LATERAL (
                SELECT mm.id
                FROM matrix mm
                WHERE mm.product_id = p.id
                    AND (mm.state_id IS NULL OR mm.state_id = %(state_id)s)
                    AND (mm.municipality_id IS NULL OR mm.municipality_id = %(municipality_id)s)
                    AND (mm.account_id IS NULL OR mm.account_id = %(account_id)s)
                    AND mm.date_init <= %(event_date)s
                    AND (mm.date_end IS NULL OR mm.date_end > %(event_date)s)
                ORDER BY
                    mm.state_id
                    ,mm.municipality_id
                    ,mm.account_id
                    ,date_init DESC
                    ,date_end
                    ,mm.in_time DESC
                    ,mm.holiday_applies DESC
                    ,mm.id DESC
                LIMIT 1
            ) AS m ON TRUE
            WHERE p.id = ANY(%(product_ids)s)
        """
        return query, params

    def get_supplier_product_matrix_lines(self, supplier_center_id: int, product_ids: list[int]):
        """ Get Matrix Lines"""
        concluded_products = self.get_supplier_products_matrix_line_ids(
            supplier_center_id,
            product_ids,
            status_ref='concluded',
        )
        concluded_matrix_ids = [x['matrix_line_id'] for x in concluded_products if x.get('matrix_line_id')]

        cancelled_products = self.get_supplier_products_matrix_line_ids(
            supplier_center_id,
            product_ids,
            status_ref='cancelled',
        )
        cancelled_matrix_ids = [x['matrix_line_id'] for x in cancelled_products if x.get('matrix_line_id')]

        return self.env['custom.supplier.cost.matrix.line'].browse(concluded_matrix_ids + cancelled_matrix_ids)

    def get_supplier_product_matrix_lines_by_supplier(self, supplier_id: int, product_ids: list[int]):
        """ Get Matrix Lines obsolete"""
        # Variables
        municipality, vehicle_category_id = self._get_event_service_variables()

        area_id = self.env['custom.geographical.area'].search([
            ('municipality_id', '=', municipality.id),
            ('partner_id.parent_id', '=', supplier_id),
            ('active', '=', True),
            ('disabled', '=', False),
        ], limit=1, order='id desc')

        supplier_center_id: int = area_id.partner_id.id
        matrix = self.env['custom.supplier.cost.matrix.line']
        if not supplier_center_id:
            return matrix  # None

        concluded_products = self.get_supplier_products_matrix_line_ids(
            supplier_center_id,
            product_ids,
            status_ref='concluded',
        )
        concluded_matrix_ids = [x['matrix_line_id'] for x in concluded_products if x.get('matrix_line_id')]

        cancelled_products = self.get_supplier_products_matrix_line_ids(
            supplier_center_id,
            product_ids,
            status_ref='cancelled',
        )
        cancelled_matrix_ids = [x['matrix_line_id'] for x in cancelled_products if x.get('matrix_line_id')]

        return matrix.browse(concluded_matrix_ids + cancelled_matrix_ids)

    def get_supplier_products_data(self, supplier_center_id: int, supplier_id: int, distance_km: int = 1):
        self.ensure_one()

        supplier_products_data = []

        # Sections
        supplier_products_data.append(Command.create({
            'display_type': 'line_section',
            'name': _('Concepts in coverage'),
            'sequence': 1,
            'covered': True,
        }))

        supplier_products_data.append(Command.create({
            'display_type': 'line_section',
            'name': _('Concepts out of coverage'),
            'sequence': 1001,
            'covered': True,
        }))

        # Product Ids
        current_product_line_ids = self.service_product_ids.filtered(
            lambda x: x.estimated_quantity > 0 and x.supplier_number == self.supplier_number
        )

        # Products Boom
        bom_products = []

        for product_line_id in current_product_line_ids:
            if not product_line_id.product_id:
                continue
            if product_line_id.base:
                bom_product_ids = self._get_boom_product(product_line_id.product_id, supplier_id)
                for product_id in bom_product_ids:
                    bom_products.append({
                        'product_line_id': product_line_id,
                        'product_id': product_id,
                        'parent_product_id': product_line_id.product_id.id,
                    })
            else:
                bom_products.append({
                    'product_line_id': product_line_id,
                    'product_id': product_line_id.product_id,
                    'parent_product_id': None,
                })

        # Matrix Lines
        matrix_cost_line_ids = self.get_supplier_product_matrix_lines(
            supplier_center_id,
            [x['product_id'].id for x in bom_products],
        )

        for product in bom_products:
            product_line_id = product['product_line_id']
            product_id = product['product_id']
            cost_line_id = matrix_cost_line_ids.filtered(
                lambda x:
                    x.concept_id.id == product_id.id
                    and x.supplier_status_id.ref == 'concluded')
            cancel_cost_line_id = matrix_cost_line_ids.filtered(
                lambda x:
                    x.concept_id.id == product_id.id
                    and x.supplier_status_id.ref == 'cancelled')

            base_unit_price = cost_line_id[0].cost if cost_line_id else 0
            base_cancel_price = cancel_cost_line_id[0].cost if cancel_cost_line_id else 0
            quantity = distance_km if product_id.x_cost_by_km else (product_line_id.estimated_quantity or 1)
            sequence = product_line_id.sequence
            if not product_line_id.covered and sequence < 1000:
                sequence += 1000
            # Add
            supplier_products_data.append(Command.create({
                'product_id': product_id.id,
                'base_quantity': quantity,
                'base_unit_price': base_unit_price,
                'base_cancel_price': base_cancel_price,
                'unit_price': base_unit_price,
                'estimated_quantity': 1,
                'quantity': quantity,
                'uom_id': product_id.uom_id.id,
                'tax_ids': [Command.set(product_id.taxes_id.ids)],
                'sequence': sequence,
                'base': product_line_id.base,
                'mandatory': product_line_id.base,
                'covered': product_line_id.covered,
                'cost_matrix_line_id': cost_line_id.id,
                'parent_product_id': product['parent_product_id'],
            }))

        return supplier_products_data

    def get_supplier_products_data_test(self, supplier_center_id: int, supplier_id: int, distance_km: int = 1):
        self.ensure_one()

        supplier_products_data = []

        # Product Ids
        current_product_line_ids = self.service_product_ids.filtered(
            lambda x: x.estimated_quantity > 0 and x.supplier_number == self.supplier_number
        )

        matrix_product_ids: list[int] = current_product_line_ids.product_id.ids

        # Product Lines
        for product_line_id in current_product_line_ids:
            if not product_line_id.product_id:
                continue
            # Product Boom
            bom_product_ids = None
            if product_line_id.base:
                bom_product_ids = self._get_boom_product(product_line_id.product_id, supplier_id)
                matrix_product_ids += bom_product_ids.ids

                for product_id in bom_product_ids:
                    quantity = distance_km if product_id.x_cost_by_km else (product_line_id.estimated_quantity or 1)

                    supplier_products_data.append({
                        'product_id': product_id.id,
                        'quantity': quantity,
                        'covered': product_line_id.covered,
                        'parent_product_id': product_line_id.product_id.id,
                    })
            # Product Base/Additional
            supplier_products_data.append({
                'product_id': product_line_id.product_id.id,
                'quantity': distance_km if product_line_id.product_id.x_cost_by_km else (product_line_id.estimated_quantity or 1),
                'covered': product_line_id.covered,
            })
        query, params = self._get_supplier_products_matrix_query(supplier_center_id, matrix_product_ids, 'concluded')
        sql = self.env.cr.mogrify(query, params)
        if isinstance(sql, bytes):
            sql = sql.decode("utf-8")

        matrix_cost_line_ids = self.get_supplier_product_matrix_lines(supplier_center_id, matrix_product_ids)

        for line in supplier_products_data:
            cost_line_id = matrix_cost_line_ids.filtered(
                lambda x:
                    x.concept_id.id == line['product_id']
                    and x.supplier_status_id.ref == 'concluded')
            cancel_cost_line_id = matrix_cost_line_ids.filtered(
                lambda x:
                    x.concept_id.id == line['product_id']
                    and x.supplier_status_id.ref == 'cancelled')
            line['base_unit_price'] = cost_line_id[0].cost if cost_line_id else 0
            line['base_cancel_price'] = cancel_cost_line_id[0].cost if cancel_cost_line_id else 0

        for line in supplier_products_data:
            if not line.get('parent_product_id'):
                line['base_unit_price'] = sum(
                    x['base_unit_price'] or 0.0
                    for x in supplier_products_data
                    if x.get('parent_product_id') == line['product_id']
                )
                line['base_cancel_price'] = sum(
                    x['base_cancel_price'] or 0.0
                    for x in supplier_products_data
                    if x.get('parent_product_id') == line['product_id']
                )

        return supplier_products_data, sql

    def _get_boom_product(self, product_id, supplier_id: int):
        product_line_id = self.env['custom.subservice.concept.line'].search([
            ('subservice_id', '=', self.sub_service_id.id),
            ('base_concept_id', '=', product_id.id),
            ('event_type_id', '=', self.event_type_id.id),
            '|',
            ('supplier_id', '=', supplier_id),
            ('supplier_id', '=', False),
        ], limit=1, order='supplier_id desc')
        if product_line_id:
            return product_line_id.concepts_ids

        return product_id

    def _get_boom_product_old(self, product_id):
        product_line_id = self.sub_service_id.concept_line_ids.filtered(
            lambda x:
                x.base_concept_id.id == product_id.id
                and x.event_type_id.id == self.event_type_id.id
        )
        if product_line_id:
            return product_line_id[0].concepts_ids

        return product_id

    def get_products_data(self):
        self.ensure_one()

        products_data = []

        # Sections
        products_data.append(Command.create({
            'display_type': 'line_section',
            'name': _('Concepts in coverage'),
            'sequence': 1,
            'covered': True,
        }))

        products_data.append(Command.create({
            'display_type': 'line_section',
            'name': _('Concepts out of coverage'),
            'sequence': 1001,
            'covered': True,
        }))

        # Product Ids
        current_product_line_ids = self.service_product_ids.filtered(
            lambda x: x.estimated_quantity > 0 and x.supplier_number == self.supplier_number
        )

        # Product Lines
        for product_line_id in current_product_line_ids:
            if not product_line_id.product_id:
                continue
            tax_ids: list[int] = product_line_id.product_id.taxes_id.ids

            # Products
            sequence = product_line_id.sequence
            if not product_line_id.covered and sequence < 1000:
                sequence += 1000

            products_data.append(Command.create({
                'product_id': product_line_id.product_id.id,
                'base_quantity': 1,
                'base_unit_price': 0,
                'base_cancel_price': 0,
                'unit_price': 0,
                'estimated_quantity': 1,
                'quantity': 1,
                'uom_id': product_line_id.uom_id.id,
                'tax_ids': [Command.set(list(set(tax_ids)))],
                'sequence': sequence,
                'covered': product_line_id.covered,
            }))
        return sorted(products_data, key=lambda x: x[2].get('sequence'))

    def _set_covered_amount(self, total_max_distance_km):
        self.ensure_one()
        membership_service_line_id = self.user_membership_id.membership_plan_id.product_line_ids.filtered(
            lambda x: self.sub_service_id in x.sub_service_ids)
        if membership_service_line_id and membership_service_line_id.limit_ids:
            limit_id = membership_service_line_id.limit_ids.filtered(
                lambda x:
                    total_max_distance_km >= x.limit_coverage_min and total_max_distance_km <= x.limit_coverage_max
                    and x.amount > self.covered_amount
            )
            if limit_id:
                self.sudo().write({
                    'covered_amount': limit_id[0].amount,
                })
                if self.authorized_amount < self.covered_amount:
                    self.sudo().write({
                        'authorized_amount': limit_id[0].amount,
                    })

    # === LOCATION METHODS === #
    def _get_external_vehicles_location(
        self,
        latitude: float, longitude: float,
        vehicle_refs: list[str],
        radius_m: float = 1000000000, max_distance_m: float = 1000000000, max_gps_age_min: float = 60000, top: int = 100,
    ):
        vehicle_data = []
        try:
            url = "https://o0c6l0kl3e.execute-api.us-east-2.amazonaws.com/nearest-vehicles"
            headers = {
                "Content-Type": "application/json",
            }
            payload = {
                "vehicle_ids": vehicle_refs,
                "destination": {"lat": latitude, "lon": longitude},
                "topX": top,
                "radius_m": radius_m,
                "max_distance_m": max_distance_m,
                "max_gps_age_min": max_gps_age_min,
            }
            # _logger.info(f"Nearest Vehicles - Payload: {payload}")
            response = requests.post(
                url,
                headers=headers, data=json.dumps(payload))
            result = response.json()
            items = result.get('items', [])
            if len(items) > 0:
                vehicle_data = [{
                    'vehicle_ref': x.get('vehicle_id', ''),
                    'lat': x.get('gps', {'lat': None, 'lon': None}).get('lat', None),
                    'lng': x.get('gps', {'lat': None, 'lon': None}).get('lon', None),
                    'distance_m': x.get('osrm', {'distance_m': 0, 'duration_s': 0}).get('distance_m', 0),
                    'duration_s': x.get('osrm', {'distance_m': 0, 'duration_s': 0}).get('duration_s', 0),
                } for x in items]
            else:
                _logger.warning(str(result))
        except Exception as e:
            _logger.error(f"Error geolocation location server: {str(e)}")
        return vehicle_data

    def get_osrm_distance(self, lat, lng, lat_dest, lng_dest):
        result = {
            'estimated_distance': 0.0,  # in km
            'estimated_duration': 0.0,  # in min
        }
        try:
            url = "https://zh90tdil2h.execute-api.us-east-2.amazonaws.com/default/route-estimate"
            headers = {
                "Content-Type": "application/json",
            }
            payload = {
                "serviceId": "SERV-223456",
                "origin": {
                    "latitude": float(lat),
                    "longitude": float(lng),
                },
                "destination": {
                    "latitude": float(lat_dest),
                    "longitude": float(lng_dest),
                },
                "date": "2026-01-01T10:30:00Z",
            }
            response = requests.post(
                url,
                headers=headers, data=json.dumps(payload))
            response_json = response.json()
            result['estimated_distance'] = response_json.get('distanceKm', 0.0)
            result['estimated_duration'] = response_json.get('estimatedTimeMinutes', 0.0)
            result['cost_distance'] = result['estimated_distance']
        except Exception as e:
            _logger.error(f"Error geolocation distance server: {str(e)}")
        # ToDo: if error, get haversine distance
        return result

    # === PROCESS METHODS === #
    def _process_suppliers_data(self, service_suppliers, assignation_type, priority=None):
        self.ensure_one()

        if len(service_suppliers) <= 0:
            return

        # Suggested Section
        suggested_section = {
            'name': _('Suggested'),
            'display_type': 'line_section',
            'assignation_type': 'electronic',
            'state': False,
            'event_id': self.id,
            'search_number': self.supplier_search_number,
            'supplier_number': self.supplier_number,
        }
        # Alternative Section
        alternatives_section = {
            'name': _('Alternatives'),
            'display_type': 'line_section',
            'assignation_type': 'electronic',
            'state': False,
            'event_id': self.id,
            'search_number': self.supplier_search_number,
            'supplier_number': self.supplier_number,
        }
        # Publication Section
        publication_section = {
            'name': _('Publication'),
            'display_type': 'line_section',
            'assignation_type': 'publication',
            'state': False,
            'event_id': self.id,
            'search_number': self.supplier_search_number,
            'supplier_number': self.supplier_number,
        }

        # Search date
        if not self.supplier_search_date:
            self.supplier_search_date = fields.Datetime.now()

        # Supplier Lines
        for supplier_id in service_suppliers:
            supplier_id['search_number'] = self.supplier_search_number
            supplier_id['supplier_number'] = self.supplier_number

        service_supplier_ids = self.env['ike.event.supplier'].create(service_suppliers)
        sequence = len(self.service_supplier_ids) - len(service_supplier_ids)
        # Add Sections and Sequence
        if assignation_type == 'electronic':
            # Suggested Section
            sequence += 1
            suggested_section['sequence'] = sequence
            self.env['ike.event.supplier'].create(suggested_section)
            # First line
            sequence += 1
            service_supplier_ids[0].sequence = sequence
            service_supplier_ids[0].ranking = 1
            # Alternatives Section
            sequence += 1
            alternatives_section['sequence'] = sequence
            self.env['ike.event.supplier'].create(alternatives_section)
            # Next lines
            for i in range(1, len(service_supplier_ids)):
                sequence += 1
                service_supplier_ids[i].sequence = sequence
                service_supplier_ids[i].ranking = i + 1
        elif assignation_type == 'publication':
            # Publication Section
            sequence += 1
            publication_section['sequence'] = sequence
            self.env['ike.event.supplier'].create(publication_section)
            # Next lines
            for i in range(0, len(service_supplier_ids)):
                sequence += 1
                service_supplier_ids[i].sequence = sequence
                service_supplier_ids[i].ranking = i + 1
        else:
            # Next lines
            for i in range(0, len(service_supplier_ids)):
                sequence += 1
                service_supplier_ids[i].sequence = sequence

    def _with_locked_records(self):
        if not self.ids:
            return []
        self._cr.execute(
            f'SELECT id FROM {self._table} WHERE id IN %s FOR UPDATE SKIP LOCKED', [tuple(self.ids)]
        )
        return [row[0] for row in self.env.cr.fetchall()]

    # === BROADCASTS === #
    def broadcastSuppliersNotifications(self):
        for rec in self:
            service_supplier_ids = rec.service_supplier_ids.filtered(lambda x: x.search_number == rec.supplier_search_number)
            if service_supplier_ids:
                suppliers = service_supplier_ids.mapped('supplier_id.id')
                for supplier in suppliers:
                    channel_name = f'ike_channel_supplier_{str(supplier)}'
                    line_ids = service_supplier_ids.filtered(lambda x: x.supplier_id.id == supplier)
                    message = {
                        'event_id': rec.id,
                        'service_supplier_ids': [
                            {
                                'id': x.id,
                                'state': x.state,
                            }
                            for x in line_ids
                        ],
                    }

                    self.env['bus.bus']._sendone(
                        target=channel_name,
                        notification_type='ike_supplier_event_search',
                        message=message,
                    )

    def broadcastSuppliersDeleted(self):
        for rec in self:
            self.env['bus.bus']._sendone(
                target='ike_channel_event_' + str(rec.id),
                notification_type='IKE_EVENT_SUPPLIERS_DELETED',
                message={
                    'id': rec.id,
                },
            )

    def broadcastEventReload(self, batch_timeout=5):
        for rec in self:
            channel_name = f'ike_channel_event_{str(rec.id)}'
            event_batcher.add_event_notification(
                self.env.cr.dbname,
                channel_name,
                'IKE_EVENT_RELOAD', {
                    'id': rec.id,
                    'state_ref': rec.stage_ref,
                    'ike_uuid': self.env.context.get('ike_uuid'),
                }, batch_timeout)

    # === ACTIONS EXTRA === #
    def action_open_add_manual_supplier_wizard(self):
        self.ensure_one()
        products_data = self.get_products_data()
        current_selected = self.selected_supplier_ids.filtered(
            lambda x: x.supplier_number == self.supplier_number
        )

        if current_selected:
            self.supplier_number += 1

        if self.supplier_search_type != 'manual_manual':
            self.supplier_search_type = 'manual_manual'
            self.supplier_search_number += 1
        return {
            'name': _('Add Supplier'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'ike.event.supplier.link',
            'view_id': self.env.ref('ike_event.ike_event_supplier_link_add_form_view').id,
            'target': 'new',
            'context': {
                'add_supplier': True,
                'from_internal': True,
                'default_event_id': self.id,
                'default_supplier_number': self.supplier_number,
                'default_supplier_product_ids': products_data,
            },
        }

    def add_manual_supplier(self, supplier_id, vehicle_id):
        self.ensure_one()

        last_line = self.env['ike.event.supplier'].search_read(
            [('event_id', '=', self.id)], ['sequence'], limit=1, order='sequence desc'
        )

        supplier_center_id: int = vehicle_id.x_center_id.id
        origin_latitude = float(self.location_latitude)
        origin_longitude = float(self.location_longitude)
        negotiation_type: str = supplier_id.x_negotiation_type
        center_latitude: float = vehicle_id.x_center_id.partner_latitude
        center_longitude: float = vehicle_id.x_center_id.partner_longitude

        # Estimated Duration/Distance
        estimated_distance_km: float = 0.0
        estimated_duration_m: float = 0.0
        total_distance_km: float = 0.0
        osrm: bool = False

        if negotiation_type in ['base_base', 'base_destination']:
            osrm_distance = self.get_osrm_distance(
                center_latitude, center_longitude,
                origin_latitude, origin_longitude
            )
            estimated_distance_km = osrm_distance['estimated_distance']
            estimated_duration_m = osrm_distance['estimated_duration']
            total_distance_km = estimated_distance_km + (self.destination_distance or 0)
            if negotiation_type == 'base_base':
                total_distance_km *= 2
        elif negotiation_type == 'origin_destination':
            total_distance_km = (self.destination_distance or 0)
        else:
            pass

        # Covered Amount
        self._set_covered_amount(total_distance_km)

        # Generals
        sequence = 1
        if last_line:
            sequence = last_line[0]['sequence'] + 1

        # Create
        event_supplier_id = self.env['ike.event.supplier'].create({
            'event_id': self.id,
            'assignation_type': 'manual_manual',
            'search_number': self.supplier_search_number,
            'supplier_number': self.supplier_number,
            'name': f"{_('License Plate')}: {vehicle_id.license_plate}",
            'supplier_id': supplier_id.id,
            'supplier_center_id': supplier_center_id,
            'negotiation_type': negotiation_type,
            'state': 'available',
            'priority': supplier_id.priority,
            'estimated_distance': estimated_distance_km,
            'estimated_duration': estimated_duration_m,
            'cost_distance': estimated_distance_km,
            'osrm': osrm,
            'timer_duration': 600,
            'is_manual': True,
            'truck_id': vehicle_id.id,  # Use real DB ID
            'assigned': vehicle_id.driver_id.display_name,
            'latitude': center_latitude,
            'longitude': center_longitude,
            'bypass': True,
            'ranking': 0,
            'sequence': sequence,
        })
        return event_supplier_id

    def action_delete_suppliers(self):
        self.ensure_one()
        for supplier_id in self.selected_supplier_ids.filtered(
            lambda x: x.state not in ('cancel', 'cancel_event', 'cancel_supplier'),
        ):
            supplier_id.truck_id.x_vehicle_service_state = 'available'
        self.broadcastSuppliersDeleted()
        self.service_supplier_ids.sudo().unlink()
        self.service_supplier_link_ids.sudo().unlink()
        self.authorization_ids.sudo().unlink()
        self.supplier_search_number = 0
        self.supplier_number = 1
        self.supplier_search_date = False
        self.authorized_amount = self.covered_amount

    def action_view_vehicles_info(self):
        self.ensure_one()

        latitude = self.location_latitude
        longitude = self.location_longitude
        if not latitude or not longitude:
            raise UserError(_('No latitude/longitude was assigned to the location.'))

        service_vehicle_type_ids, service_accessory_ids = self._get_event_sub_service_variables()

        vehicle_ids = self.env['fleet.vehicle'].search([
            ('disabled', '=', False),
            ('driver_id', '!=', False),
            ('x_vehicle_type', 'in', service_vehicle_type_ids),
            ('x_vehicle_service_state', '=', 'available'),
        ])

        vehicles = [{
            'vehicle_id': vehicle_id.id,  # Keep real DB ID
            'vehicle_ref': vehicle_id.x_vehicle_ref,
            'supplier_center_id': vehicle_id.x_center_id.id,
            'latitude': vehicle_id.x_latitude,
            'longitude': vehicle_id.x_longitude,
            'distance_km': 0,
            'duration_m': 0,
            'external_location': False,
            'external_latitude': None,
            'external_longitude': None,
            'external_distance_km': 0,
            'external_duration_m': 0,
        } for vehicle_id in vehicle_ids]

        vehicles_location_data = self._get_external_vehicles_location(
            float(self.location_latitude),
            float(self.location_longitude),
            [str(x.x_vehicle_ref) for x in vehicle_ids],
            1000000000,
            1000000000,
        )
        for vehicle in vehicles:
            data = next(
                (x for x in vehicles_location_data if x['vehicle_ref'] == vehicle['vehicle_ref']),
                None
            )
            if data:
                vehicle['external_latitude'] = data.get('lat', None)
                vehicle['external_longitude'] = data.get('lng', None)
                vehicle['external_distance_km'] = data.get('distance_m', 0) / 1000
                vehicle['external_duration_m'] = data.get('duration_s', 0) / 60
                vehicle['external_location'] = True
                if not vehicle['external_distance_km']:
                    vehicle['external_location'] = False
                    vehicle['external_distance_km'] = round(
                        self.haversine_distance_km(
                            float(self.location_latitude),
                            float(self.location_latitude),
                            float(vehicle["external_latitude"] or 0),
                            float(vehicle["external_latitude"] or 0),
                        ),
                        2
                    )
                    vehicle['external_duration_m'] = self.get_estimated_duration(vehicle['external_distance_km'])
            if vehicle['latitude'] and vehicle['longitude']:
                osrm_distance = self.get_osrm_distance(
                    vehicle['latitude'], vehicle['longitude'],
                    self.location_latitude, self.location_longitude,
                )
                vehicle['distance_km'] = osrm_distance['estimated_distance']
                vehicle['duration_m'] = osrm_distance['estimated_duration']

        wizard_id = self.env['ike.event.vehicle.wizard'].create({
            'event_id': self.id,
            'vehicle_ids': [Command.create(vehicle) for vehicle in vehicles if vehicle['latitude'] or vehicle['external_latitude']]
        })
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vehicles',
            'res_model': 'ike.event.vehicle.wizard',
            'res_id': wizard_id.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {}
        }

    # === MULTI SUPPLIERS ACTIONS (OBSOLETE?) === #
    def action_add_multi_supplier_product_data(self):
        self.ensure_one()
        numbers = self.service_supplier_ids.mapped('supplier_number')
        self.supplier_number = max(numbers) + 1 if numbers else 1
        self.supplier_search_number += 1
        self.step_number = 2
        if self._is_base_supplier():
            self.action_set_products_covered()

    def action_add_multi_supplier_supplier_data(self):
        self.ensure_one()
        self.step_number = 3

    def action_add_multi_supplier_continue(self):
        self.ensure_one()
        current_selected = self.selected_supplier_ids.filtered(lambda x: x.supplier_number == self.supplier_number)
        if not current_selected:
            raise ValidationError(_('You must have a supplier selected.'))
        self.step_number = 1

    # === STATIC METHODS === #
    @staticmethod
    def get_estimated_duration(distance):
        # ToDo: Better Estimated Duration
        km_per_hour = 50
        if distance > 100:
            km_per_hour = 70
        elif distance > 10:
            km_per_hour = 60
        else:
            km_per_hour = 40
        return round(distance * 1.2 / km_per_hour * 60, 2)

    @staticmethod
    def haversine_distance_km(origin_latitude, origin_longitude, destination_latitude, destination_longitude):
        earth_radius_km = 6371

        origin_latitude_rad = math.radians(origin_latitude)
        destination_latitude_rad = math.radians(destination_latitude)

        latitude_difference_rad = math.radians(
            destination_latitude - origin_latitude
        )
        longitude_difference_rad = math.radians(
            destination_longitude - origin_longitude
        )

        haversine_value = (
            math.sin(latitude_difference_rad / 2) ** 2
            + math.cos(origin_latitude_rad)
            * math.cos(destination_latitude_rad)
            * math.sin(longitude_difference_rad / 2) ** 2
        )

        angular_distance = 2 * math.atan2(
            math.sqrt(haversine_value),
            math.sqrt(1 - haversine_value),
        )

        distance_km = earth_radius_km * angular_distance
        return distance_km
