from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PortalAccount(CustomerPortal):

    def _get_ike_event_trucks_domain(self):
        return []

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'ike_event_truck_count' in counters:
            values['ike_event_truck_count'] = request.env['fleet.vehicle'].search_count(self._get_ike_event_trucks_domain(), limit=1)
        return values

    # Lista de proveedores
    @http.route(['/provider/portal/trucks', '/provider/portal/trucks/page/<int:page>'], type='http', auth="user", website=True)
    def portal_events_truck(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, plate_search=None,
                            model_search=None, status_search=None, driver_search=None, **kw):
        try:
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
        except Exception as e:
            _logger.error("Error in portal_events_truck: %s", str(e))
            return request.redirect('/my')

    @http.route(['/provider/portal/trucks/available_drivers'], type='json', auth='user')
    def get_available_drivers(self, center_of_attention_id, **kw):
        """
        Get all drivers from a supplier that are NOT assigned to any vehicle
        """
        try:
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
        except Exception as e:
            return {'error': str(e)}

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
