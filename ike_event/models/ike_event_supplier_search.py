# -*- coding: utf-8 -*-

import json
import logging
import math
import requests

from datetime import timedelta
from psycopg2.errors import LockNotAvailable

from odoo import models, fields, api, Command, _
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
    supplier_search_number = fields.Integer(string='Search Number (Supplier)', default=0, copy=False)
    base_supplier_number = fields.Integer(default=1, copy=False)
    is_searching = fields.Boolean(default=False, copy=False)
    next_search_uuid = fields.Char(copy=False)
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

        # Algorithm
        service_suppliers, max_suppliers, limit_max_distance_km = self._search_suppliers_algorithm(assignation_type, priority)

        if len(service_suppliers):
            # Supplier products with costs
            current_authorization_ids = self.authorization_ids.filtered(lambda x: x.supplier_number <= self.supplier_number)
            # Max Distance by Supplier
            supplier_max_distances = {}
            max_distance_km: float = 0.0
            for item in service_suppliers:
                if item['estimated_distance'] > max_distance_km:
                    max_distance_km = item['estimated_distance']
                if item['estimated_distance'] > supplier_max_distances.get(item['supplier_id'], 0):
                    supplier_max_distances[item['supplier_id']] = item['estimated_distance']

            # Covered Amount
            self._set_covered_amount(max_distance_km + (self.destination_distance or 0))

            # Supplies
            for supplier in service_suppliers:
                supplier_link_id = self.service_supplier_link_ids.filtered(
                    lambda x:
                        x.supplier_id.id == supplier['supplier_id']
                        and x.supplier_number == self.supplier_number,
                )
                # Distance km
                total_distance_km = supplier_max_distances.get(supplier['supplier_id'], 0) + (self.destination_distance or 0)
                total_distance_km = int(-(-total_distance_km // 1))

                # Supplier Link
                if not supplier_link_id:
                    supplier_products_data = self.get_supplier_products_data(supplier['supplier_id'], total_distance_km)
                    for product_data in supplier_products_data:
                        product_data[2]['supplier_number'] = self.supplier_number

                    has_zero = any(
                        d[2].get('product_id', None) and d[2]['base_unit_price'] == 0
                        for d in supplier_products_data
                    )
                    if has_zero:
                        supplier['ignore'] = True
                    supplier_link_id = self.env['ike.event.supplier.link'].with_context(from_internal=True).create({
                        'event_id': self.id,
                        'supplier_id': supplier['supplier_id'],
                        'supplier_number': self.supplier_number,
                        'supplier_product_ids': supplier_products_data,
                    })
                    # Set Authorization Data
                    authorized = (self.previous_amount + supplier_link_id.estimated_cost) <= self.authorized_amount
                    for product_id in supplier_link_id.supplier_product_ids:
                        if authorized:
                            product_id.authorization_pending = False or not product_id.covered
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

                # Set link totals
                supplier['supplier_link_id'] = supplier_link_id.id
                supplier['estimated_cost'] = supplier_link_id.amount_concept_total

                # Electronic Search ignore
                if assignation_type == 'electronic' and supplier['estimated_cost'] > self.authorized_amount:
                    supplier['ignore'] = True

            # Filter and Sort Suppliers by
            service_suppliers = sorted(
                [item for item in service_suppliers if not item.get('ignore')],
                key=lambda x: (x['estimated_duration'], x['estimated_cost'], -int(x['priority']))
            )
            service_suppliers = service_suppliers[:max_suppliers]

            # Set Google Route
            if assignation_type == 'electronic':
                for supplier in service_suppliers:
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

    # === ALGORITHM === #
    def _search_suppliers_algorithm(self, assignation_type, priority=None) -> tuple[list[dict], int, float]:
        """ Algorithm """
        self.ensure_one()
        service_suppliers = []

        # * LOGGER 0: Start
        _logger.info(f"IKE EVENT - DEBUG - 0: {assignation_type} {str(priority)}")

        # Global Variables
        sequence_conf = 1
        # To Filter supplier geographical areas
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
            # ? Raise 1
            # raise UserError(_("There are no municipalities with postal code: %s.", zip_code))
            return [], max_suppliers, max_radius_km

        # * LOGGER 2: Municipalities
        municipalities_text = ','.join([f'{x['id']}.{x['name']}' for x in municipalities_data])
        _logger.info(f"IKE EVENT - DEBUG - 2: {municipalities_text}")

        # Get Supplier Centers
        supplier_centers_data = self._get_supplier_centers(assignation_type_conf, municipalities_data)
        if not len(supplier_centers_data):
            # ? Raise 2
            # raise UserError(_(
            #     "There are no geographic areas configured for this municipality: %s (%s).",
            #     municipalities_text, zip_code,
            # ))
            return [], max_suppliers, max_radius_km

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
                ('x_latitude', '!=', False),
                ('x_longitude', '!=', False),
            ]

            # Federal Plates
            if self.requires_federal_plates:
                vehicles_domain.append(
                    ('x_federal_license_plates', '=', True),
                )
            # Accessories & Maneuvers
            if len(service_accessory_ids):
                vehicles_domain.append(('x_maneuvers', '=', True))
                for accessory_id in service_accessory_ids:
                    vehicles_domain.append(('x_accessories', 'in', [accessory_id]))
            else:
                # Maneuvers
                product_tag_names = self.service_product_ids.mapped('product_id.product_tag_ids.name')
                if 'maniobras' in product_tag_names:
                    vehicles_domain.append(('x_maneuvers', '=', True))

            # * LOGGER 4: Vehicles Domain
            _logger.info("IKE EVENT - DEBUG - 4: %s", vehicles_domain)

            # Search Vehicles
            service_vehicle_ids = self.env['fleet.vehicle'].search(vehicles_domain, order='x_center_id')
            service_vehicles_data = [{
                'id': rec.id,
                'driver_id': [rec.driver_id.id, rec.driver_id.name],
                'license_plate': rec.license_plate,
                'vehicle_type': rec.vehicle_type,
                'x_partner_id': [rec.x_partner_id.id, None],
                'x_center_id': [rec.x_center_id.id, None],
                'x_latitude': rec.x_latitude,
                'x_longitude': rec.x_longitude,
            } for rec in service_vehicle_ids]

            # Get External Location/Duration/Distance
            if self.use_external_locations:
                vehicles_location_data = self._get_external_vehicles_location(
                    float(latitude),
                    float(longitude),
                    vehicle_refs=[str(x.x_vehicle_ref) for x in service_vehicle_ids],
                    radius_m=float(max_radius_km * 1000),
                    max_distance_m=float(max_radius_km * 1.4 * 1000),
                )
                if len(vehicles_location_data):
                    for i, vehicle_id in enumerate(service_vehicle_ids):
                        data = next(
                            (x for x in vehicles_location_data if x['vehicle_ref'] == vehicle_id.x_vehicle_ref),
                            None
                        )
                        if data:
                            vehicle_id.x_latitude = data.get('lat', None)
                            vehicle_id.x_longitude = data.get('lng', None)
                            service_vehicles_data[i]['x_latitude'] = data.get('lat', None)
                            service_vehicles_data[i]['x_longitude'] = data.get('lng', None)
                            service_vehicles_data[i]['estimated_distance'] = data.get('distance_m', 0) / 1000
                            service_vehicles_data[i]['estimated_duration'] = data.get('duration_s', 0) / 60
                            service_vehicles_data[i]['osrm'] = True

            # Get Estimated Duration/Distance and priority
            supplier_center_data = {'supplier_center_id': 0}
            for vehicle in service_vehicles_data:
                if supplier_center_data['supplier_center_id'] != vehicle['x_center_id'][0]:
                    supplier_center_data = next(
                        (x for x in supplier_centers_data if x['supplier_center_id'] == vehicle['x_center_id'][0]),
                        {}
                    )
                vehicle['priority'] = supplier_center_data['priority']
                if not vehicle.get('estimated_distance', False):
                    estimated_distance_km = round(
                        self.haversine_distance_km(
                            float(latitude),
                            float(longitude),
                            float(vehicle["x_latitude"]),
                            float(vehicle["x_longitude"]),
                        ),
                        2
                    )
                    vehicle['estimated_distance'] = estimated_distance_km
                    vehicle['estimated_duration'] = self.get_estimated_duration(estimated_distance_km)

            # * LOGGER 5: Service Vehicles
            vehicles_text = ", ".join([
                f"{x['id']}.{x['license_plate']} ({str(x['estimated_distance'])}, {str(x['estimated_duration'])})"
                for x in service_vehicles_data
            ])
            _logger.info(f"IKE EVENT - DEBUG - 5: ({str(max_radius_km)}, {str(max_arrived_time_m)}), {vehicles_text}")

            # Filter vehicles max distance/duration
            service_vehicles_data = [
                x for x in service_vehicles_data
                if (
                    (
                        x.get('osrm')
                        and x['estimated_distance'] <= (max_radius_km * 1.5)
                        and x['estimated_duration'] <= (max_arrived_time_m * 1.5)
                    )
                    or (
                        x['estimated_distance'] <= max_radius_km
                        and x['estimated_duration'] <= max_arrived_time_m
                    )
                )
            ]
            service_vehicles_len = len(service_vehicles_data)

            for i in range(0, service_vehicles_len):
                vehicle = service_vehicles_data[i]
                service_suppliers.append({
                    'event_id': self.id,
                    'assignation_type': assignation_type,
                    'name': f"{_('License Plate')}: {vehicle['license_plate']}",
                    'supplier_id': vehicle['x_partner_id'][0],
                    'supplier_center_id': vehicle['x_center_id'][0],
                    'state': 'available',
                    'priority': vehicle['priority'],
                    'estimated_distance': vehicle['estimated_distance'],
                    'estimated_duration': vehicle['estimated_duration'],
                    'timer_duration': timer_duration_s,
                    'osrm': vehicle.get('osrm'),
                    'is_manual': False,
                    'truck_id': vehicle['id'],  # Set the correct db ID
                    'assigned': vehicle['driver_id'][1] if vehicle['driver_id'] else "",
                    'latitude': vehicle['x_latitude'],
                    'longitude': vehicle['x_longitude'],
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
        vehicle_category_id = res_id.vehicle_nus_id.vehicle_category_id.id  # type: ignore
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

    def _get_supplier_centers(self, assignation_type_conf: str, municipalities_data: list):
        supplier_centers_query = """
            SELECT DISTINCT
                ga.partner_id as supplier_center_id
                ,ga.parent_id as supplier_id
                ,ga.priority
                ,su.x_is_special_accounts
                ,su.x_is_exclusive_accounts
                ,gap.product_id
            FROM custom_geographical_area ga
            INNER JOIN res_partner su on su.id = ga.parent_id
            INNER JOIN custom_geographical_area_product_rel gap on gap.geographical_area_id = ga.id
            WHERE
                ga.municipality_id IN %s
                AND NOT ga.disabled AND ga.active
                AND NOT su.disabled AND su.active
                AND gap.product_id = %s
        """
        supplier_centers_query += assignation_type_conf

        municipality_ids = tuple(x['id'] for x in municipalities_data)
        self._cr.execute(supplier_centers_query, [municipality_ids, self.sub_service_id.id])
        supplier_centers_data = self._cr.dictfetchall()

        return supplier_centers_data

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

    def get_supplier_products_matrix_line_ids(
        self,
        supplier_id: int,
        product_ids: list[int],
        status_ref: str,
    ):
        """ Get Matrix Lines ids by Query """

        # Variables
        municipality, vehicle_category_id = self._get_event_service_variables()

        if not municipality:
            return []

        if not vehicle_category_id:
            vehicle_category = self.env['fleet.vehicle.model.category'].search([
                ('name', '=', 'Auto'),
            ])
            vehicle_category_id = vehicle_category.id

        area_id = self.env['custom.geographical.area'].search([
            ('municipality_id', '=', municipality.id),
            ('partner_id.parent_id', '=', supplier_id),
            ('active', '=', True),
            ('disabled', '=', False),
        ], limit=1, order='id desc')
        if not area_id:
            return []

        supplier_center_id: int = area_id.partner_id.id
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

        params = (
            event_time,
            is_holiday,
            supplier_center_id,
            sub_service_id,
            event_type_id,
            vehicle_category_id,
            status_ref,
            state_id,
            municipality_id,
            account_id,
            event_date,
            event_date,
            product_ids,
        )

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
                    ,CASE WHEN %s BETWEEN start_time AND end_time THEN 1 ELSE 0 END AS in_time
                    ,m.holiday_date_applies::int = %s as holiday_applies
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
                    AND supplier_center_id = %s
                    AND m.subservice_id = %s
                    AND m.type_event_id = %s
                    AND svc.vehicle_category_id = %s
                    AND st.ref = %s
            )
            SELECT
                p.id AS product_id,
                m.id AS matrix_line_id
            FROM product_product p
            JOIN LATERAL (
                SELECT mm.id
                FROM matrix mm
                WHERE mm.product_id = p.id
                    AND (mm.state_id IS NULL OR mm.state_id = %s)
                    AND (mm.municipality_id IS NULL OR mm.municipality_id = %s)
                    AND (mm.account_id IS NULL OR mm.account_id = %s)
                    AND date_init <= %s
                    AND (date_end IS NULL OR date_end > %s)
                ORDER BY
                    mm.state_id,
                    mm.municipality_id,
                    mm.account_id,
                    date_init DESC,
                    date_end,
                    mm.in_time DESC,
                    mm.holiday_applies DESC,
                    mm.id DESC
                LIMIT 1
            ) AS m ON TRUE
            WHERE p.id = ANY(%s)
        """
        # query_result = query % params
        # print(query_result)

        self.env.cr.execute(query, params)
        return self.env.cr.dictfetchall()

    def get_supplier_product_matrix_lines(self, supplier_id: int, product_ids: list[int]):
        """ Get Matrix Lines"""
        concluded_products = self.get_supplier_products_matrix_line_ids(
            supplier_id=supplier_id,
            product_ids=product_ids,
            status_ref='concluded',
        )
        concluded_matrix_ids = [x['matrix_line_id'] for x in concluded_products if x.get('matrix_line_id')]

        cancelled_products = self.get_supplier_products_matrix_line_ids(
            supplier_id=supplier_id,
            product_ids=product_ids,
            status_ref='cancelled',
        )
        cancelled_matrix_ids = [x['matrix_line_id'] for x in cancelled_products if x.get('matrix_line_id')]

        return self.env['custom.supplier.cost.matrix.line'].browse(concluded_matrix_ids + cancelled_matrix_ids)

    def get_supplier_products_data(self, supplier_id: int, distance_km: int = 1):
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

        # Matrix Lines
        matrix_cost_line_ids = self.get_supplier_product_matrix_lines(supplier_id, current_product_line_ids.mapped('product_id.id'))

        # Product Lines
        for product_line_id in current_product_line_ids:
            if not product_line_id.product_id:
                continue
            # Product Boom
            product_ids = None
            total_base_unit_price = 0
            total_base_cancel_price = 0
            tax_ids: list[int] = product_line_id.product_id.taxes_id.ids
            if product_line_id.base:
                product_ids = self._get_boom_product(product_line_id.product_id)
                tax_ids = product_ids.mapped('taxes_id.id')
                boom_matrix_cost_line_ids = self.get_supplier_product_matrix_lines(
                    supplier_id,
                    product_ids.ids
                )
                for product_id in product_ids:
                    cost_line_id = boom_matrix_cost_line_ids.filtered(
                        lambda x:
                            x.concept_id.id == product_id.id
                            and x.supplier_status_id.ref == 'concluded')
                    cancel_cost_line_id = boom_matrix_cost_line_ids.filtered(
                        lambda x:
                            x.concept_id.id == product_id.id
                            and x.supplier_status_id.ref == 'cancelled')

                    base_unit_price = cost_line_id[0].cost if cost_line_id else 0
                    base_cancel_price = cancel_cost_line_id[0].cost if cancel_cost_line_id else 0
                    quantity = distance_km if product_id.x_cost_by_km else (product_line_id.estimated_quantity or 1)
                    total_base_unit_price += (base_unit_price * quantity)
                    total_base_cancel_price += base_cancel_price
                    sequence = product_line_id.sequence
                    if not product_line_id.covered and sequence < 1000:
                        sequence += 1000

                    supplier_products_data.append(Command.create({
                        'product_id': product_id.id,
                        'base_unit_price': base_unit_price,
                        'base_cancel_price': base_cancel_price,
                        'unit_price': base_unit_price,
                        'estimated_quantity': 1,
                        'quantity': quantity,
                        'uom_id': product_id.uom_id.id,
                        'tax_ids': [Command.set(product_id.taxes_id.ids)],
                        'sequence': sequence,
                        'covered': product_line_id.covered,
                        'cost_matrix_line_id': cost_line_id.id,
                        'parent_product_id': product_line_id.product_id.id,
                    }))
            # Product Base/Additional
            cost_line_id = None
            cancel_cost_line_id = None
            if not product_line_id.base:
                cost_line_id = matrix_cost_line_ids.filtered(
                    lambda x:
                        x.concept_id.id == product_line_id.product_id.id
                        and x.supplier_status_id.ref == 'concluded')
                cancel_cost_line_id = matrix_cost_line_ids.filtered(
                    lambda x:
                        x.concept_id.id == product_line_id.product_id.id
                        and x.supplier_status_id.ref == 'cancelled')
                total_base_unit_price = cost_line_id[0].cost if cost_line_id else 0
                total_base_cancel_price = cancel_cost_line_id[0].cost if cancel_cost_line_id else 0

            sequence = product_line_id.sequence
            if not product_line_id.covered and sequence < 1000:
                sequence += 1000

            supplier_products_data.append(Command.create({
                'product_id': product_line_id.product_id.id,
                'base_unit_price': total_base_unit_price,
                'base_cancel_price': total_base_cancel_price,
                'unit_price': total_base_unit_price,
                'estimated_quantity': 1,
                'quantity': distance_km if product_line_id.product_id.x_cost_by_km else (product_line_id.estimated_quantity or 1),
                'uom_id': product_line_id.uom_id.id,
                'tax_ids': [Command.set(list(set(tax_ids)))],
                'sequence': sequence,
                'covered': product_line_id.covered,
                'cost_matrix_line_id': cost_line_id.id if cost_line_id else None,
            }))
        return supplier_products_data

    def _get_boom_product(self, product_id):
        product_line_id = self.sub_service_id.concept_line_ids.filtered(
            lambda x:
                x.base_concept_id.id == product_id.id
                and x.event_type_id.id == self.event_type_id.id
        )
        if product_line_id:
            return product_line_id[0].concepts_ids

        return product_id

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
            if rec.service_supplier_ids:
                suppliers = rec.service_supplier_ids.mapped('supplier_id.id')
                for supplier in suppliers:
                    channel_name = f'ike_channel_supplier_{str(supplier)}'
                    line_ids = rec.service_supplier_ids.filtered(lambda x: x.supplier_id.id == supplier)
                    message = {
                        'event_id': rec.id,
                        'service_supplier_ids': [
                            {
                                'id': x.id,
                            }
                            for x in line_ids
                        ],
                    }

                    self.env['bus.bus']._sendone(
                        target=channel_name,
                        notification_type='ike_supplier_event_deleted',
                        message=message,
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
                }, batch_timeout)

    # === ACTIONS EXTRA === #
    def action_open_add_manual_supplier_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add Supplier',
            'res_model': 'ike.event.manual.supplier.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_event_id': self.id,
            }
        }

    def add_manual_suppliers_wizard(self, supplier_id, vehicle_id):
        self.ensure_one()

        self.service_supplier_ids.filtered(lambda x: x.state == 'notified').action_expire()

        current_selected = self.selected_supplier_ids.filtered(
            lambda x: x.supplier_number == self.supplier_number
        )

        if current_selected:
            self.supplier_number += 1

        if self.supplier_search_type != 'manual_manual':
            self.supplier_search_type = 'manual_manual'
            self.supplier_search_number += 1

        last_line = self.env['ike.event.supplier'].search_read(
            [('event_id', '=', self.id)], ['sequence'], limit=1, order='sequence desc'
        )

        # Estimated Duration/Distance
        estimated_distance_km = 0.0
        estimated_duration_m = 0.0
        osrm = False
        if self.use_external_locations:
            vehicles_location_data = self._get_external_vehicles_location(
                float(self.location_latitude),
                float(self.location_longitude),
                vehicle_refs=[str(vehicle_id.x_vehicle_ref)]
            )
            if len(vehicles_location_data):
                data = vehicles_location_data[0]
                vehicle_id.x_latitude = data.get('lat', None)
                vehicle_id.x_longitude = data.get('lng', None)
                estimated_distance_km = data.get('distance_m', 0) / 1000
                estimated_duration_m = data.get('duration_s', 0) / 60
                osrm = True
        if not estimated_distance_km and vehicle_id.x_latitude and vehicle_id.x_longitude:
            estimated_distance_km = round(
                self.haversine_distance_km(
                    float(self.location_latitude),
                    float(self.location_longitude),
                    float(vehicle_id.x_latitude),
                    float(vehicle_id.x_longitude)
                ),
                2
            )
            estimated_duration_m = self.get_estimated_duration(estimated_distance_km)
        # Distance km
        total_distance_km = estimated_distance_km + (self.destination_distance or 0)
        total_distance_km = int(-(-total_distance_km // 1))

        # Covered Amount
        self._set_covered_amount(total_distance_km)

        # Generals
        sequence = 1
        if last_line:
            sequence = last_line[0]['sequence'] + 1

        current_authorization_ids = self.authorization_ids.filtered(lambda x: x.supplier_number <= self.supplier_number)

        supplier_link_id = self.service_supplier_link_ids.filtered(
            lambda x:
                x.supplier_id.id == supplier_id.id
                and x.supplier_number == self.supplier_number,
        )
        # Supplier Link
        if not supplier_link_id:
            supplier_products_data = self.get_supplier_products_data(supplier_id.id, total_distance_km)
            supplier_link_id = self.env['ike.event.supplier.link'].with_context(from_internal=True).create({
                'event_id': self.id,
                'supplier_id': supplier_id.id,
                'supplier_number': self.supplier_number,
                'supplier_product_ids': supplier_products_data,
            })
            # Set Authorization Data
            authorized = (self.previous_amount + supplier_link_id.estimated_cost) <= self.authorized_amount
            for product_id in supplier_link_id.supplier_product_ids:
                if authorized and product_id.subtotal > 0:
                    product_id.authorization_pending = False or not product_id.covered
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

        # Create
        self.service_supplier_ids = [Command.create({
            'event_id': self.id,
            'assignation_type': 'manual_manual',
            'search_number': self.supplier_search_number,
            'supplier_number': self.supplier_number,
            'is_manual': True,
            'name': f"{_('License Plate')}: {vehicle_id.license_plate}",
            'supplier_id': supplier_id.id,
            'supplier_center_id': vehicle_id.x_center_id.id,
            'state': 'available',
            'priority': supplier_id.priority,
            'estimated_distance': estimated_distance_km,
            'estimated_duration': estimated_duration_m,
            'osrm': osrm,
            'timer_duration': 600,
            'truck_id': vehicle_id.id,  # Use real DB ID
            'assigned': vehicle_id.driver_id.display_name,
            'latitude': vehicle_id.x_latitude,
            'longitude': vehicle_id.x_longitude,
            'supplier_link_id': supplier_link_id.id,
            'ranking': 0,
            'sequence': sequence,
        })]

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
                vehicle['distance_km'] = round(
                    self.haversine_distance_km(
                        float(self.location_latitude),
                        float(self.location_latitude),
                        float(vehicle["latitude"]),
                        float(vehicle["latitude"]),
                    ),
                    2
                )
                vehicle['duration_m'] = self.get_estimated_duration(vehicle['distance_km'])

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

    # === SUPPLIER SEARCH ACTIONS FOR JAVASCRIPT === #
    def next_search_suppliers(self, params):
        """ Process executed from JavaScript to handle the concurrency problems. """
        self.ensure_one()
        is_searching = False
        try:
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "SELECT id FROM %s WHERE id = %%s FOR UPDATE" % self._table,
                    (self.id,)
                )
                self.env.cr.execute(
                    "SELECT is_searching, next_search_uuid FROM %s WHERE id = %%s" % self._table,
                    (self.id,)
                )
                row = self.env.cr.fetchone()

                if row and (row[0] is True or row[1] != params['next_uuid']):
                    is_searching = True
                if not is_searching:
                    self.env.cr.execute(
                        "UPDATE %s SET is_searching = true WHERE id = %%s" % self._table,
                        (self.id,)
                    )
        except Exception:
            return

        if is_searching:
            return

        try:
            method = getattr(self, params['function_name'], None)
            if callable(method):
                method(params)
        except UserError:
            raise
        except Exception as e:
            _logger.exception("Unexpected error (id=%s): %s", self.id, e)
        finally:
            self.write({'is_searching': False, 'next_search_uuid': None})

    def search_publication_suppliers_3(self, params):
        self.ensure_one()
        if self.next_search_uuid == params['next_uuid']:
            self.next_search_uuid = None
            self._search_suppliers('publication', '3')

    def search_publication_suppliers_2(self, params):
        self.ensure_one()
        if self.next_search_uuid == params['next_uuid']:
            self.next_search_uuid = None
            self._search_suppliers('publication', '2')

    def search_publication_suppliers_1(self, params):
        self.ensure_one()
        if self.next_search_uuid == params['next_uuid']:
            self.next_search_uuid = None
            self._search_suppliers('publication', '1')

    def search_publication_suppliers_0(self, params):
        self.ensure_one()
        if self.next_search_uuid == params['next_uuid']:
            self.next_search_uuid = None
            self._search_suppliers('publication', '0')

    def search_manual_suppliers(self, params):
        self.ensure_one()
        if self.next_search_uuid == params['next_uuid']:
            self.next_search_uuid = None
            self._search_suppliers('manual')

    # === MULTI SUPPLIERS ACTIONS === #
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
