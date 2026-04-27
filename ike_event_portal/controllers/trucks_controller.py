from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PortalAccount(CustomerPortal):

    def _get_ike_event_trucks_domain(self):
        return []

    @http.route(['/provider/portal/trucks/get_accessories_domain'], type='json', auth='user')
    def get_accessories_domain(self):
        """Get the domain for accessories from product.product model"""
        return request.env['product.product'].get_accessories_domain()

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'ike_event_truck_count' in counters:
            values['ike_event_truck_count'] = request.env['fleet.vehicle'].search_count(self._get_ike_event_trucks_domain(), limit=1)
        return values

    # Lista de proveedores
    @http.route(['/provider/portal/trucks', '/provider/portal/trucks/page/<int:page>'], type='http', auth="user", website=True)
    def portal_events_truck(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, plate_search=None,
                            model_search=None, status_search=None, driver_search=None, **kw):
        _logger.info("Accessing portal_events_truck: " + str(request.env.user.has_group('ike_event_portal.custom_group_portal_supervisor')))
        if not request.env.user.has_group('ike_event_portal.custom_group_portal_admin') and not request.env.user.has_group('ike_event_portal.custom_group_portal_supervisor'):
            return request.redirect('/my')

        trucks = request.env['fleet.vehicle']
        domain = self._get_ike_event_trucks_domain()

        # 2. Apply the selected filter
        if not filterby:
            filterby = 'all'

        if not sortby:
            sortby = 'date'
        # sort_order = searchbar_sortings[sortby]['order']

        if plate_search:
            domain.append(('license_plate', 'ilike', plate_search))

        if model_search:
            domain.append(('model_id.name', 'ilike', model_search))

        if driver_search:
            domain.append(('driver_id.name', 'ilike', driver_search))

        # Count records matching the domain
        truck_count = trucks.search_count(domain)

        pager = portal_pager(
            url="/provider/portal/trucks",
            url_args={'sortby': sortby, 'filterby': filterby},
            total=truck_count,
            page=page,
            step=self._items_per_page
        )
        trucks = trucks.search(domain)

        # 3. Pass the filters to the template
        values = {
            'trucks': trucks,
            'page_name': 'fleet',
            'pager': pager,
            'sortby': sortby,
            'filterby': filterby,
            'plate_search': plate_search,
            'model_search': model_search,
            'driver_search': driver_search,
            'default_url': '/event/portal/trucks'
        }
        return request.render("ike_event_portal.portal_ike_event_trucks", values)

    # Vista de un proveedor
    @http.route(['/provider/portal/truck/<int:truck_id>'], type='http', auth="user", website=True)
    def portal_truck_detail(self, truck_id, **kw):
        try:
            # Fetch the truck record using sudo() to ensure access if rules are strict
            truck = request.env['fleet.vehicle'].sudo().browse(truck_id)

            # Check if the record exists
            if not truck.exists():
                return request.redirect('/provider/portal/trucks')

        except (AccessError, MissingError):
            return request.redirect('/provider/portal/trucks')

        values = {
            'truck': truck,
            'page_name': 'truck_detail',
        }
        return request.render("ike_event_portal.portal_ike_event_truck_detail", values)

    # Route to display the creation form
    @http.route(['/provider/portal/truck/new'], type='http', auth="user", website=True)
    def portal_new_truck_form(self, **kw):
        # Fetch data for dropdowns, based on the custom model
        values = {
            'page_name': 'new_truck',
            'models': request.env['fleet.vehicle.model'].search([]),
            'suppliers': request.env['res.partner'].search([
                ('x_is_supplier', '=', True),
                ('disabled', '=', False)
            ]),
            'vehicle_types': request.env['custom.vehicle.type'].search([
                ('disabled', '=', False)
            ]),
            'drivers': request.env['res.partner'].search([]),  # The domain is dynamic, so we fetch all for the portal
            'service_states': dict(request.env['fleet.vehicle'].with_context(lang=request.env.user.lang)._fields['x_vehicle_service_state'].selection),
            'accessories': request.env['product.product'].search([
                ('disabled', '=', False),
                ('x_accessory_ok', '=', True)
            ]),
        }
        return request.render("ike_event_portal.portal_ike_event_truck_new", values)

    # Route to process the form submission
    @http.route(['/provider/portal/truck/create'], type='http', auth="user", website=True, methods=['POST'])
    def portal_create_truck(self, **kw):
        """
        Receives form data from the new truck portal form and creates a new fleet.vehicle record.
        """
        # Redirect to the new truck's detail page
        return request.redirect('/provider/portal/trucks')

    # Route to display the creation form
    @http.route(['/provider/portal/supplier/new'], type='http', auth="user", website=True)
    def portal_new_supplier(self, **kw):
        # Fetch potential drivers for the dropdown
        drivers = request.env['res.partner'].search([])
        values = {
            'drivers': drivers,
            'page_name': 'new_supplier',
        }
        return request.render("ike_event_portal.portal_create_supplier", values)

    # Route to process the form submission
    @http.route(['/provider/portal/supplier/create'], type='http', auth="user", website=True, methods=['POST'])
    def portal_create_supplier(self, **kw):
        # Prepare values for creation
        vals = {
            'name': kw.get('name'),
            'email': kw.get('email'),
            'vehicle_registration': kw.get('vehicle_registration'),
            'vehicle_model': kw.get('vehicle_model'),
            'vehicle_type': kw.get('vehicle_type'),
            'service': kw.get('service'),
            'status': kw.get('status'),
            # Handle Many2one field safely
            'assigned_driver_id': int(kw.get('assigned_driver_id')) if kw.get('assigned_driver_id') else False,
        }

        # Create the new partner record
        new_supplier = request.env['res.partner'].create(vals)

        # Redirect to the new supplier's detail page
        return request.redirect('/provider/portal/supplier/%s' % new_supplier.id)

    @http.route(['/provider/portal/trucks/available_drivers'], type='json', auth='user')
    def get_available_drivers(self, center_of_attention_id, **kw):
        """
        Get all drivers from a supplier that are NOT assigned to any vehicle
        """
        # 1. Get all driver IDs already assigned to vehicles
        assigned_drivers = request.env['fleet.vehicle'].sudo().search([
            ('driver_id', '!=', False)
        ]).mapped('driver_id.id')

        # 2. Get all drivers for this supplier
        supplier_relations = request.env['res.partner.supplier_users.rel'].sudo().search([
            ('center_of_attention_id', '=', center_of_attention_id),
            ('user_type', '=', 'operator')
        ])
        supplier_driver_ids = supplier_relations.mapped('partner_id.id')

        # 3. Filter out assigned drivers
        available_driver_ids = list(set(supplier_driver_ids) - set(assigned_drivers))

        # 4. Return the partner records
        drivers = request.env['res.partner'].sudo().browse(available_driver_ids).read(['id', 'name'])

        return drivers

    @http.route(['/provider/portal/trucks/accessories'], type='json', auth='user')
    def get_accessories(self, **kw):
        """
        Get all available accessories for trucks
        """
        try:
            # Get accessories domain from product.product model
            accessories_domain = request.env['product.product'].get_accessories_domain()

            # Search accessories with the domain
            accessories = request.env['product.product'].sudo().search_read(
                accessories_domain,
                ['id', 'name', 'display_name']
            )

            return {
                'success': True,
                'accessories': accessories
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    @http.route(['/provider/portal/trucks/can_edit_driver'], type='json', auth='user')
    def can_edit_driver(self, **kw):
        """
        Check if the current user has permission to edit truck drivers
        Returns True if user is in the portal admin or supervisor group
        """
        try:
            # Check if user has admin or supervisor group
            can_edit = (
                request.env.user.has_group('ike_event_portal.custom_group_portal_supervisor')
            )

            return {
                'success': True,
                'can_edit': can_edit
            }
        except Exception as e:
            return {
                'success': False,
                'can_edit': False,
                'error': str(e)
            }

    @http.route(['/provider/portal/trucks/can_add_driver'], type='json', auth='user')
    def can_add_driver(self, **kw):
        """
        Check if the current user has permission to add truck drivers
        Returns True if user is in the portal admin or supervisor group
        """
        try:
            # Check if user has admin or supervisor group
            can_edit = (
                request.env.user.has_group('ike_event_portal.custom_group_portal_admin')
            )

            return {
                'success': True,
                'can_edit': can_edit
            }
        except Exception as e:
            return {
                'success': False,
                'can_edit': False,
                'error': str(e)
            }

    @http.route(['/provider/portal/trucks/update_driver'], type='json', auth='user')
    def update_truck_driver(self, truck_id, driver_id, **kw):
        """
        Update the driver_id field of a fleet.vehicle record
        """
        try:
            truck = request.env['fleet.vehicle'].sudo().browse(truck_id)

            if not truck.exists():
                return {
                    'success': False,
                    'error': 'Truck not found'
                }

            # Update the driver
            truck.write({'driver_id': driver_id if driver_id else False})

            return {
                'success': True,
                'message': 'Driver updated successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
