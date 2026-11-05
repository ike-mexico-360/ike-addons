import base64
import io

import xlsxwriter
from odoo import SUPERUSER_ID, fields, http, _
from odoo.exceptions import UserError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import content_disposition, request
import logging

_logger = logging.getLogger(__name__)


class PortalAccount(CustomerPortal):

    # These are the only columns a portal user may hide. Economic number and
    # actions intentionally do not belong here because they are always shown.
    _TRUCK_OPTIONAL_COLUMNS = {
        'license_plate', 'model', 'vehicle_type', 'driver',
        'state', 'current_event', 'last_change',
    }

    def _get_ike_event_trucks_domain(self):
        return []

    @http.route('/provider/portal/trucks/column_preferences', type='json', auth='user')
    def truck_column_preferences(self, visible_columns=None, **kwargs):
        """Read or save the current portal user's truck-list column choices."""
        user = request.env.user
        if not (
            user.has_group('ike_event_portal.custom_group_portal_admin')
            or user.has_group('ike_event_portal.custom_group_portal_supervisor')
        ):
            return {'success': False, 'error': _('You do not have access to truck preferences.')}

        if visible_columns is None:
            return {
                'success': True,
                'visible_columns': user.sudo().x_portal_truck_visible_columns,
            }

        if not isinstance(visible_columns, list):
            return {'success': False, 'error': _('Invalid column preferences.')}

        selected_columns = [
            column for column in visible_columns
            if column in self._TRUCK_OPTIONAL_COLUMNS
        ]
        user.sudo().write({'x_portal_truck_visible_columns': selected_columns})
        return {'success': True, 'visible_columns': selected_columns}

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

    @http.route(['/provider/portal/trucks/can_edit_status'], type='json', auth='user')
    def can_edit_status(self, **kw):
        """Return whether the user is a provider portal administrator.

        Changing a unit's operating status is deliberately separate from
        driver editing: only the provider administrator may do it.
        """
        try:
            return {
                'success': True,
                'can_edit': request.env.user.has_group(
                    'ike_event_portal.custom_group_portal_admin'
                ),
            }
        except Exception as error:
            return {'success': False, 'can_edit': False, 'error': str(error)}

    @http.route(['/provider/portal/trucks/not_available_reasons'], type='json', auth='user')
    def not_available_reasons(self, **kw):
        """Expose the same temporary-unavailability catalog used by the form."""
        try:
            field = request.env['fleet.vehicle']._fields['x_reason_not_available']
            selection = field._description_selection(request.env)
            return {
                'success': True,
                'reasons': [
                    {'value': value, 'label': label}
                    for value, label in selection
                ],
            }
        except Exception as error:
            return {'success': False, 'reasons': [], 'error': str(error)}

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

    @http.route(['/provider/portal/trucks/vehicle_types'], type='json', auth='user')
    def get_vehicle_types(self, **kw):
        try:
            types = request.env['custom.vehicle.type'].sudo().search_read(
                [], ['id', 'name']
            )
            return {'success': True, 'vehicle_types': types}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route(['/provider/portal/trucks/centers'], type='json', auth='user')
    def get_centers(self, **kw):
        try:
            user_id = request.env.user
            request.env.cr.execute("""
                SELECT supplier_id AS id
                FROM res_partner_supplier_users_rel
                WHERE user_id = %s
            """, (user_id.id,))
            result = request.env.cr.fetchone()
            supplier_id = result[0] if result else 0
            centers = request.env['res.partner'].sudo().search_read(
                [('parent_id', '=', supplier_id), ('x_is_center', '=', True)],
                ['id', 'name']
            )
            return {'success': True, 'centers': centers}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route(['/provider/portal/trucks/update_fields'], type='json', auth='user')
    def update_truck_fields(self, truck_id, fields, **kw):
        try:
            truck = request.env['fleet.vehicle'].sudo().browse(truck_id)
            if not truck.exists():
                return {'success': False, 'error': 'Truck not found'}
            allowed = {'x_vehicle_type', 'x_center_id', 'license_plate', 'x_maneuvers', 'x_federal_license_plates', 'x_manages_tire_conditioning', 'x_vehicles_axes'}
            vals = {k: v for k, v in fields.items() if k in allowed}
            truck.write(vals)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route(['/provider/portal/trucks/update_status'], type='json', auth='user')
    def update_truck_status(self, truck_id, new_state, temporary_reason=None, estimated_return_date=None, **kw):
        try:
            if not request.env.user.has_group(
                'ike_event_portal.custom_group_portal_admin'
            ):
                return {
                    'success': False,
                    'error': _('You do not have permission to change the unit status.'),
                }

            truck = request.env['fleet.vehicle'].sudo().browse(truck_id)
            if not truck.exists():
                return {'success': False, 'error': _('Truck not found')}

            supplier_ids = request.env[
                'res.partner.supplier_users.rel'
            ].sudo().search([
                ('user_id', '=', request.env.user.id),
            ]).mapped('supplier_id').ids
            if truck.x_partner_id.id not in supplier_ids:
                return {
                    'success': False,
                    'error': _('The truck does not belong to your supplier.'),
                }

            current_state = truck.x_vehicle_service_state
            if new_state == current_state:
                return {'success': True}
            allowed_transitions = {
                ('not_available', 'available'),
                ('available', 'not_available'),
            }
            if (current_state, new_state) not in allowed_transitions:
                return {
                    'success': False,
                    'error': _('This unit status transition is not allowed.'),
                }

            if current_state == 'not_available' and new_state == 'available':
                if truck.x_current_event_info:
                    return {
                        'success': False,
                        'error': _(
                            'The unit status cannot be changed while the truck has an event in progress.'
                        ),
                    }

            values = {'x_vehicle_service_state': new_state}
            if current_state == 'available' and new_state == 'not_available':
                valid_reasons = dict(
                    truck._fields['x_reason_not_available']._description_selection(
                        request.env
                    )
                )
                if temporary_reason not in valid_reasons or not estimated_return_date:
                    return {'success': False, 'error': _('A reason and estimated return date are required for temporary unavailability.')}
                values.update({
                    # Keep the portal aligned with the existing vehicle-form
                    # catalog; it is a selection, never free text.
                    'x_reason_not_available': temporary_reason,
                    'x_not_available_return_date': estimated_return_date,
                })
            truck.write(values)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _portal_deregistration_vehicle(self, truck_id):
        """Return a supplier-owned truck only for a provider portal administrator."""
        user = request.env.user
        if not user.has_group('ike_event_portal.custom_group_portal_admin'):
            raise UserError(_('Only the provider administrator can permanently deregister a unit.'))
        truck = request.env['fleet.vehicle'].sudo().browse(int(truck_id)).exists()
        if not truck:
            raise UserError(_('Truck not found'))
        supplier_ids = request.env['res.partner.supplier_users.rel'].sudo().search([
            ('user_id', '=', user.id),
        ]).mapped('supplier_id').ids
        if truck.x_partner_id.id not in supplier_ids:
            raise UserError(_('The truck does not belong to your supplier.'))
        return truck

    @http.route(['/provider/portal/trucks/deregistration/reasons'], type='json', auth='user')
    def permanent_deregistration_reasons(self, **kw):
        reason_field = request.env['fleet.vehicle']._fields['x_reason_permanent_deregistration']
        reasons = [
            {'id': key, 'name': label}
            for key, label in reason_field._description_selection(request.env)
        ]
        return {'success': True, 'reasons': reasons}

    @http.route(['/provider/portal/trucks/deregistration/check'], type='json', auth='user')
    def check_permanent_deregistration(self, truck_id, **kw):
        """Validate before displaying the first permanent-deregistration confirmation."""
        try:
            truck = self._portal_deregistration_vehicle(truck_id)
            validation = truck.portal_deregistration_check()
            return {
                'success': True,
                'truck': {
                    'id': truck.id,
                    'economic_number': truck.x_economic_number or '',
                    'license_plate': truck.license_plate or '',
                    'vehicle_type': truck.x_vehicle_type.display_name or '',
                },
                **validation,
            }
        except Exception as error:
            return {'success': False, 'error': str(error)}

    @http.route(['/provider/portal/trucks/deregistration/eligibility'], type='json', auth='user')
    def permanent_deregistration_eligibility(self, truck_ids, **kw):
        """Return whether each list-row may show the permanent-deregistration action."""
        eligible = {}
        try:
            if not request.env.user.has_group('ike_event_portal.custom_group_portal_admin'):
                return {'success': True, 'eligible': eligible}
            truck_ids = [int(truck_id) for truck_id in (truck_ids or []) if str(truck_id).isdigit()]
            for truck in request.env['fleet.vehicle'].sudo().browse(truck_ids).exists():
                try:
                    self._portal_deregistration_vehicle(truck.id)
                    truck.portal_deregistration_check()
                    eligible[truck.id] = True
                except Exception:
                    eligible[truck.id] = False
            return {'success': True, 'eligible': eligible}
        except Exception:
            # A pre-check error must hide the optional action, rather than
            # displaying an option that will fail immediately.
            return {'success': True, 'eligible': eligible}

    @http.route(['/provider/portal/trucks/deregistration/history'], type='json', auth='user')
    def permanent_deregistration_history(self, truck_id, **kw):
        try:
            truck = self._portal_deregistration_vehicle(truck_id)
            if truck.x_vehicle_service_state != 'deregistration':
                return {'success': False, 'error': _('This unit has not been permanently deregistered.')}
            return {'success': True, 'history': {
                'economic_number': truck.x_deregistration_economic_number,
                'license_plate': truck.x_deregistration_license_plate,
                'reason': truck._permanent_deregistration_reason_name(),
                'date': fields.Datetime.to_string(truck.x_deregistration_date) if truck.x_deregistration_date else '',
                'user': truck.x_deregistration_user_id.name or '',
                # Do not expose the generic /web/content URL here.  Portal
                # users do not have direct access to arbitrary attachments;
                # each download goes through the route below, which verifies
                # that the attachment belongs to this supplier's unit.
                'evidence': [{
                    'id': attachment.id,
                    'name': attachment.name,
                    'download_url': '/provider/portal/trucks/deregistration/evidence/%s/%s' % (
                        truck.id, attachment.id,
                    ),
                } for attachment in truck.x_deregistration_evidence_ids],
            }}
        except Exception as error:
            return {'success': False, 'error': str(error)}

    @http.route(
        '/provider/portal/trucks/deregistration/evidence/<int:truck_id>/<int:attachment_id>',
        type='http', auth='user', methods=['GET'], website=True,
    )
    def download_permanent_deregistration_evidence(self, truck_id, attachment_id, **kw):
        """Download one evidence file after validating portal ownership."""
        try:
            truck = self._portal_deregistration_vehicle(truck_id)
            attachment = truck.x_deregistration_evidence_ids.filtered(
                lambda record: record.id == attachment_id,
            )
            if not attachment:
                return request.not_found()
            content = base64.b64decode(attachment.datas or b'')
            headers = [
                ('Content-Type', attachment.mimetype or 'application/octet-stream'),
                ('Content-Disposition', content_disposition(attachment.name)),
            ]
            return request.make_response(content, headers=headers)
        except Exception:
            # Avoid revealing attachment or vehicle information through this
            # endpoint when the portal user does not own the unit.
            return request.not_found()

    @http.route(['/provider/portal/trucks/deregistration/request_code'], type='json', auth='user')
    def request_permanent_deregistration_code(self, truck_id, reason, license_plate, evidence=None, **kw):
        """First confirmation: plate matching, evidence, then a 10-minute code."""
        try:
            truck = self._portal_deregistration_vehicle(truck_id)
            if (license_plate or '').strip().upper() != (truck.license_plate or '').strip().upper():
                return {'success': False, 'error': _('The license plate confirmation does not match the unit.')}
            validation = truck.portal_request_deregistration_code(request.env.user, reason, evidence)
            return {'success': True, **validation}
        except Exception as error:
            return {'success': False, 'error': str(error)}

    @http.route(['/provider/portal/trucks/deregistration/confirm'], type='json', auth='user')
    def confirm_permanent_deregistration(self, truck_id, code, **kw):
        """Second confirmation: verify the code and permanently deregister the unit."""
        try:
            truck = self._portal_deregistration_vehicle(truck_id)
            truck.portal_confirm_deregistration(request.env.user, code)
            return {'success': True}
        except Exception as error:
            return {'success': False, 'error': str(error)}

    @http.route(['/provider/portal/trucks/deregistration/cancel'], type='json', auth='user')
    def cancel_permanent_deregistration(self, truck_id, **kw):
        try:
            truck = self._portal_deregistration_vehicle(truck_id)
            truck.portal_cancel_deregistration(request.env.user)
            return {'success': True}
        except Exception as error:
            return {'success': False, 'error': str(error)}

    @http.route(['/provider/portal/trucks/last_state_changes'], type='json', auth='user')
    def get_last_state_changes(self, truck_ids, **kw):
        """
        Return the last x_vehicle_service_state change logged in the chatter for each truck:
        {truck_id: {'date': 'YYYY-MM-DD HH:MM:SS' (UTC), 'user': name, 'is_system': bool}}
        """
        try:
            # Only trucks the current user can read.
            trucks = request.env['fleet.vehicle'].search([('id', 'in', truck_ids)])
            changes = self._get_last_state_changes(trucks)
            for change in changes.values():
                change['date'] = fields.Datetime.to_string(change['date'])
            return {'success': True, 'changes': changes}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @http.route(['/provider/portal/trucks/current_event_summary'], type='json', auth='user')
    def get_current_event_summary(self, truck_id, **kw):
        """Portal summary HTML of the truck's current event (see fleet.vehicle.x_current_event_info)."""
        try:
            # Only a truck the current user can read, and only its current event.
            truck = request.env['fleet.vehicle'].search([('id', '=', truck_id)], limit=1)
            info = truck.x_current_event_info
            if not info:
                return {'success': False, 'error': _('The truck has no event in progress.')}
            supplier_line = request.env['ike.event.supplier'].sudo().browse(info['id'])
            return {
                'success': True,
                'event_name': info['event_name'],
                'stage': info['stage_name'],
                'summary': supplier_line.event_supplier_summary_data_portal or '',
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _get_last_state_changes(self, trucks):
        """{truck_id: {'date': datetime (UTC), 'user': name, 'is_system': bool}} from the chatter log."""
        # Portal users cannot read tracking values, hence sudo.
        tracking_values = request.env['mail.tracking.value'].sudo().search([
            ('field_id.model', '=', 'fleet.vehicle'),
            ('field_id.name', '=', 'x_vehicle_service_state'),
            ('mail_message_id.model', '=', 'fleet.vehicle'),
            ('mail_message_id.res_id', 'in', trucks.ids),
        ], order='id desc')

        partner_root = request.env.ref('base.partner_root')
        result = {}
        for tracking in tracking_values:
            message = tracking.mail_message_id
            if message.res_id in result:
                continue
            # Changes made by crons/automations run as OdooBot (superuser).
            is_system = message.create_uid.id == SUPERUSER_ID or message.author_id == partner_root
            result[message.res_id] = {
                'date': message.date,
                'user': '' if is_system else (message.author_id.name or message.create_uid.name),
                'is_system': is_system,
            }
        return result

    @http.route(['/provider/portal/trucks/download/xlsx'], type='http', auth='user', website=True)
    def portal_trucks_xlsx(self, ids='', **kw):
        """Export the trucks shown in the portal list, in the order given by `ids` (comma-separated)."""
        truck_ids = [int(truck_id) for truck_id in ids.split(',') if truck_id.strip().isdigit()]
        # Only trucks the current user can read; keep the list's sort order.
        trucks_by_id = {truck.id: truck for truck in request.env['fleet.vehicle'].search([('id', 'in', truck_ids)])}
        trucks = [trucks_by_id[truck_id] for truck_id in truck_ids if truck_id in trucks_by_id]

        last_changes = self._get_last_state_changes(request.env['fleet.vehicle'].browse(list(trucks_by_id)))
        # Website route: request.env carries the page language, so labels match the list.
        state_labels = dict(
            request.env['fleet.vehicle']._fields['x_vehicle_service_state']._description_selection(request.env)
        )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(_('Service Units'))

        header_format = workbook.add_format({
            'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#16006F',
            'border': 1, 'border_color': '#16006F', 'align': 'center', 'valign': 'vcenter',
        })
        text_format = workbook.add_format({'border': 1, 'border_color': '#DFE3F1', 'valign': 'top'})
        datetime_format = workbook.add_format({
            'border': 1, 'border_color': '#DFE3F1', 'valign': 'top', 'num_format': 'dd/mm/yyyy hh:mm',
        })

        headers = [
            _('Economic number'), _('License plate'), _('Federal'), _('Make / model'), _('Year'), _('Vehicle type'),
            _('Driver'), _('Status'), _('Last change'), _('Last change user'),
        ]
        for column, title in enumerate(headers):
            worksheet.write(0, column, title, header_format)
        worksheet.set_column('A:B', 16)
        worksheet.set_column('C:C', 10)
        worksheet.set_column('D:D', 30)
        worksheet.set_column('E:E', 8)
        worksheet.set_column('F:H', 22)
        worksheet.set_column('I:I', 18)
        worksheet.set_column('J:J', 26)

        for row, truck in enumerate(trucks, start=1):
            last_change = last_changes.get(truck.id)
            worksheet.write(row, 0, truck.x_economic_number or 'N/A', text_format)
            worksheet.write(row, 1, truck.license_plate or 'N/A', text_format)
            worksheet.write(row, 2, _('Yes') if truck.x_federal_license_plates else _('No'), text_format)
            worksheet.write(row, 3, truck.model_id.display_name or _('Generic'), text_format)
            worksheet.write(row, 4, truck.model_year or 'N/A', text_format)
            worksheet.write(row, 5, truck.x_vehicle_type.display_name or 'N/A', text_format)
            worksheet.write(row, 6, truck.driver_id.name or _('Unassigned'), text_format)
            worksheet.write(row, 7, state_labels.get(truck.x_vehicle_service_state, 'N/A'), text_format)
            if last_change:
                # xlsxwriter has no timezone support: write the time as the user sees it.
                local_date = fields.Datetime.context_timestamp(request.env.user, last_change['date'])
                worksheet.write_datetime(row, 8, local_date.replace(tzinfo=None), datetime_format)
                worksheet.write(row, 9, 'Sistema' if last_change['is_system'] else last_change['user'], text_format)
            else:
                worksheet.write(row, 8, '-', text_format)
                worksheet.write(row, 9, '', text_format)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(trucks), len(headers) - 1)
        workbook.close()
        xlsx_content = output.getvalue()

        return request.make_response(
            xlsx_content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Length', len(xlsx_content)),
                ('Content-Disposition', content_disposition('unidades_de_servicio.xlsx')),
            ],
        )

    @http.route(['/provider/portal/trucks/download/detailed/xlsx'], type='http', auth='user', website=True)
    def portal_trucks_detailed_xlsx(self, ids='', **kw):
        """Export filtered trucks with the complete operational data set and UUID."""
        truck_ids = [int(truck_id) for truck_id in ids.split(',') if truck_id.strip().isdigit()]
        trucks_by_id = {
            truck.id: truck
            for truck in request.env['fleet.vehicle'].search([('id', 'in', truck_ids)])
        }
        trucks = [trucks_by_id[truck_id] for truck_id in truck_ids if truck_id in trucks_by_id]
        last_changes = self._get_last_state_changes(request.env['fleet.vehicle'].browse(list(trucks_by_id)))
        state_labels = dict(
            request.env['fleet.vehicle']._fields['x_vehicle_service_state']._description_selection(request.env)
        )

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet(_('Detailed service units'))
        header_format = workbook.add_format({
            'bold': True, 'font_color': '#FFFFFF', 'bg_color': '#16006F',
            'border': 1, 'border_color': '#16006F', 'align': 'center', 'valign': 'vcenter',
        })
        text_format = workbook.add_format({'border': 1, 'border_color': '#DFE3F1', 'valign': 'top'})
        datetime_format = workbook.add_format({
            'border': 1, 'border_color': '#DFE3F1', 'valign': 'top', 'num_format': 'dd/mm/yyyy hh:mm',
        })
        headers = [
            _('Economic number'), _('License plate'), _('Federal plates'),
            _('Make / model'), _('Year'), _('Vehicle type'), _('Driver'),
            _('Status'), _('Current event'), _('Event stage'), _('Last change'),
            _('Last change user'), _('Attention center'), _('Vehicle UUID'),
        ]
        for column, title in enumerate(headers):
            worksheet.write(0, column, title, header_format)
        worksheet.set_column('A:B', 16)
        worksheet.set_column('C:C', 14)
        worksheet.set_column('D:D', 30)
        worksheet.set_column('E:E', 8)
        worksheet.set_column('F:J', 22)
        worksheet.set_column('K:K', 18)
        worksheet.set_column('L:M', 26)
        worksheet.set_column('N:N', 38)

        for row, truck in enumerate(trucks, start=1):
            last_change = last_changes.get(truck.id)
            current_event = truck.x_current_event_info or {}
            worksheet.write(row, 0, truck.x_economic_number or 'N/A', text_format)
            worksheet.write(row, 1, truck.license_plate or 'N/A', text_format)
            worksheet.write(row, 2, _('Yes') if truck.x_federal_license_plates else _('No'), text_format)
            worksheet.write(row, 3, truck.model_id.display_name or _('Generic'), text_format)
            worksheet.write(row, 4, truck.model_year or 'N/A', text_format)
            worksheet.write(row, 5, truck.x_vehicle_type.display_name or 'N/A', text_format)
            worksheet.write(row, 6, truck.driver_id.name or _('Unassigned'), text_format)
            worksheet.write(row, 7, state_labels.get(truck.x_vehicle_service_state, 'N/A'), text_format)
            worksheet.write(row, 8, current_event.get('event_name') or 'N/A', text_format)
            worksheet.write(row, 9, current_event.get('stage_name') or 'N/A', text_format)
            if last_change:
                local_date = fields.Datetime.context_timestamp(request.env.user, last_change['date'])
                worksheet.write_datetime(row, 10, local_date.replace(tzinfo=None), datetime_format)
                worksheet.write(row, 11, _('System') if last_change['is_system'] else last_change['user'], text_format)
            else:
                worksheet.write(row, 10, '-', text_format)
                worksheet.write(row, 11, '', text_format)
            worksheet.write(row, 12, truck.x_center_id.display_name or 'N/A', text_format)
            worksheet.write(row, 13, truck.x_vehicle_ref or 'N/A', text_format)

        worksheet.freeze_panes(1, 0)
        worksheet.autofilter(0, 0, len(trucks), len(headers) - 1)
        workbook.close()

        generated_at = fields.Datetime.context_timestamp(request.env.user, fields.Datetime.now())
        filename = '%s_%s.xlsx' % (_('detailed_service_units'), generated_at.strftime('%Y%m%d_%H%M%S'))
        xlsx_content = output.getvalue()
        return request.make_response(
            xlsx_content,
            headers=[
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Length', len(xlsx_content)),
                ('Content-Disposition', content_disposition(filename)),
            ],
        )

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
