from datetime import datetime, time, timedelta

from pytz import UTC, timezone

from odoo import _, fields, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import request
from odoo.tools import html2plaintext


class ClientEventsPortal(CustomerPortal):

    def _get_portal_client(self):
        partner = request.env.user.partner_id
        checked_partners = request.env['res.partner']
        current_partner = partner
        while current_partner and current_partner not in checked_partners:
            checked_partners |= current_partner
            if current_partner.x_is_client:
                return current_partner
            current_partner = current_partner.parent_id
        if partner.commercial_partner_id.x_is_client:
            return partner.commercial_partner_id
        return request.env['res.partner']

    def _get_client_accounts(self, client):
        if not client:
            return request.env['res.partner']
        accounts = client.x_account_child_ids.filtered(lambda account: not account.disabled)
        if client.x_is_account and not client.disabled:
            accounts |= client
        return accounts.sorted(lambda account: account.name or '')

    def _get_client_event_domain(self, accounts):
        return [('account_id', 'in', accounts.ids)] if accounts else [('id', '=', 0)]

    def _get_event_vehicle_data(self, event):
        vehicle_data = {'description': '-'}
        if event.service_res_model != 'ike.service.input.vial' or not event.service_res_id:
            return vehicle_data

        vial = request.env[event.service_res_model].sudo().browse(event.service_res_id).exists()
        if not vial:
            return vehicle_data

        vehicle_parts = [
            vial.vehicle_brand,
            vial.vehicle_model,
            vial.vehicle_year,
            vial.vehicle_color,
            vial.vehicle_plate,
        ]
        vehicle_data['description'] = ' - '.join(part for part in vehicle_parts if part) or '-'

        return vehicle_data

    @staticmethod
    def _apply_mask(value, mask):
        if not value:
            return '-'
        if not mask:
            return value

        value = str(value)
        mask = str(mask)
        if len(mask) < len(value):
            mask += '#' * (len(value) - len(mask))

        result = []
        value_index = 0
        for character in mask:
            if value_index >= len(value):
                break
            result.append(value[value_index] if character == '#' else character)
            value_index += 1
        return ''.join(result)

    @staticmethod
    def _format_eta(minutes):
        if not minutes:
            return '-'
        total_minutes = max(round(minutes), 0)
        hours, remaining_minutes = divmod(total_minutes, 60)
        return f'{hours:02d}:{remaining_minutes:02d}'

    @staticmethod
    def _prepare_eta_semaphore(supplier):
        eta = {
            'class': 'bg-light text-dark border',
            'display': '-',
            'label': _('No ETA'),
            'style': '',
        }
        if not supplier:
            return eta

        now = fields.Datetime.now()
        if supplier.finalized_date:
            concluded_hours = max((now - supplier.finalized_date).total_seconds(), 0) / 3600
            if concluded_hours <= 24:
                eta.update({
                    'class': 'bg-success text-white',
                    'display': _('≤ 24 hours'),
                    'label': _('Provider completed'),
                })
            elif concluded_hours <= 48:
                eta.update({
                    'class': 'bg-warning text-dark',
                    'display': _('≤ 48 hours'),
                    'label': _('Provider completed'),
                })
            else:
                eta.update({
                    'class': 'bg-danger text-white',
                    'display': _('≤ 72 hours') if concluded_hours <= 72 else _('> 72 hours'),
                    'label': _('Provider completed'),
                })
            return eta

        if supplier.contacted_date:
            eta.update({
                'class': 'bg-primary text-white',
                'display': _('Provider contacted'),
                'label': _('Provider contacted'),
            })
            return eta

        duration_minutes = max(supplier.estimated_duration or 0, 0)
        start_date = supplier.assignation_date
        if not duration_minutes or not start_date:
            return eta

        eta['display'] = ClientEventsPortal._format_eta(duration_minutes)
        deadline = start_date + timedelta(minutes=duration_minutes)
        elapsed_seconds = max((now - start_date).total_seconds(), 0)
        progress = elapsed_seconds / (duration_minutes * 60)

        if now > deadline:
            eta.update({'class': 'bg-danger text-white', 'label': _('Expired')})
        elif progress <= (1 / 3):
            eta.update({'class': 'bg-success text-white', 'label': _('On time')})
        elif progress <= (2 / 3):
            eta.update({'class': 'bg-warning text-dark', 'label': _('On time')})
        else:
            eta.update({
                'class': 'text-white',
                'label': _('Due soon'),
                'style': 'background-color: #fd7e14;',
            })
        return eta

    def _prepare_event_rows(self, events):
        rows = []
        encryption_utility = request.env['custom.encryption.utility'].sudo()
        for event in events:
            suppliers = event.selected_supplier_ids
            supplier = suppliers.sorted(
                lambda item: item.assignation_date or fields.Datetime.from_string('1970-01-01')
            )[-1:]
            assignation_dates = [date for date in suppliers.mapped('assignation_date') if date]
            contacted_dates = [date for date in suppliers.mapped('contacted_date') if date]
            vehicle_data = self._get_event_vehicle_data(event)
            eta_semaphore = self._prepare_eta_semaphore(supplier)
            encrypted_client_name = event.user_id.name if event.user_id else ''
            encrypted_account_code = event.user_membership_id.key_identification or ''
            client_name = (
                encryption_utility.decrypt_aes256(encrypted_client_name)
                if encrypted_client_name
                else event.nu_name
            )
            account_code = (
                encryption_utility.decrypt_aes256(encrypted_account_code)
                if encrypted_account_code
                else ''
            )
            rows.append({
                'event': event,
                'client': client_name or '-',
                'account_code': self._apply_mask(account_code, event.membership_display_mask),
                'vehicle': vehicle_data['description'],
                'origin': html2plaintext(event.location_label or '').strip() or '-',
                'destination': html2plaintext(event.destination_label or '').strip() or '-',
                'assignation_date': max(assignation_dates, default=False),
                'contacted_date': max(contacted_dates, default=False),
                'eta': self._format_eta(supplier.estimated_duration if supplier else 0),
                'eta_display': eta_semaphore['display'],
                'eta_class': eta_semaphore['class'],
                'eta_label': eta_semaphore['label'],
                'eta_style': eta_semaphore['style'],
            })
        return rows

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        client = self._get_portal_client()
        if client and 'client_event_count' in counters:
            accounts = self._get_client_accounts(client)
            values['client_event_count'] = request.env['ike.event'].sudo().search_count(
                self._get_client_event_domain(accounts)
            )
        return values

    def _prepare_portal_layout_values(self):
        values = super()._prepare_portal_layout_values()
        values['is_client_portal'] = bool(self._get_portal_client())
        return values

    @http.route(
        ['/my/events', '/my/events/page/<int:page>'],
        type='http',
        auth='user',
        website=True,
    )
    def portal_client_events(
        self,
        page=1,
        account_id=None,
        stage_id=None,
        service_id=None,
        assignation_date_from=None,
        assignation_date_to=None,
        contacted_date_from=None,
        contacted_date_to=None,
        search=None,
        sortby='date_desc',
        items_per_page=10,
        **kwargs,
    ):
        client = self._get_portal_client()
        if not client:
            return request.redirect('/my')

        accounts = self._get_client_accounts(client)
        event_model = request.env['ike.event'].sudo()
        domain = self._get_client_event_domain(accounts)

        selected_account_id = self._safe_integer(account_id)
        if selected_account_id in accounts.ids:
            domain.append(('account_id', '=', selected_account_id))
        else:
            selected_account_id = False

        visible_accounts = accounts.filtered(
            lambda account: not selected_account_id or account.id == selected_account_id
        )
        account_identifier_names = {
            account.x_account_identification_id.name or False
            for account in visible_accounts
        }
        account_identifier_label = (
            next(iter(account_identifier_names))
            if len(account_identifier_names) == 1 and False not in account_identifier_names
            else _('Account identifier')
        )

        base_events = event_model.search(self._get_client_event_domain(accounts))
        available_stages = base_events.mapped('stage_id').sorted(lambda stage: stage.sequence)
        available_services = base_events.mapped('service_id').sorted(lambda service: service.name or '')

        selected_stage_id = self._safe_integer(stage_id)
        if selected_stage_id in available_stages.ids:
            domain.append(('stage_id', '=', selected_stage_id))
        else:
            selected_stage_id = False

        selected_service_id = self._safe_integer(service_id)
        if selected_service_id in available_services.ids:
            domain.append(('service_id', '=', selected_service_id))
        else:
            selected_service_id = False

        parsed_assignation_date_from = self._safe_date(assignation_date_from)
        parsed_assignation_date_to = self._safe_date(assignation_date_to)
        parsed_contacted_date_from = self._safe_date(contacted_date_from)
        parsed_contacted_date_to = self._safe_date(contacted_date_to)
        if parsed_assignation_date_from or parsed_assignation_date_to:
            assignation_domain = []
            if parsed_assignation_date_from:
                assignation_domain.append((
                    'assignation_date',
                    '>=',
                    self._local_date_bound(parsed_assignation_date_from, time.min),
                ))
            if parsed_assignation_date_to:
                assignation_domain.append((
                    'assignation_date',
                    '<=',
                    self._local_date_bound(parsed_assignation_date_to, time.max),
                ))
            domain.append((
                'selected_supplier_ids',
                'any',
                assignation_domain,
            ))
        if parsed_contacted_date_from or parsed_contacted_date_to:
            contacted_domain = []
            if parsed_contacted_date_from:
                contacted_domain.append((
                    'contacted_date',
                    '>=',
                    self._local_date_bound(parsed_contacted_date_from, time.min),
                ))
            if parsed_contacted_date_to:
                contacted_domain.append((
                    'contacted_date',
                    '<=',
                    self._local_date_bound(parsed_contacted_date_to, time.max),
                ))
            domain.append((
                'selected_supplier_ids',
                'any',
                contacted_domain,
            ))

        if search:
            search = search.strip()
            if search:
                domain.append(('name', 'ilike', search))

        sortings = {
            'date_desc': {'label': _('Newest'), 'order': 'event_date desc, id desc'},
            'date_asc': {'label': _('Oldest'), 'order': 'event_date asc, id asc'},
            'expedient': {'label': _('Expedient'), 'order': 'name asc'},
        }
        if sortby not in sortings:
            sortby = 'date_desc'

        items_per_page = self._safe_integer(items_per_page)
        if items_per_page not in (10, 25, 50, 100):
            items_per_page = 10

        event_count = event_model.search_count(domain)
        url_args = {
            'account_id': selected_account_id or '',
            'stage_id': selected_stage_id or '',
            'service_id': selected_service_id or '',
            'assignation_date_from': assignation_date_from or '',
            'assignation_date_to': assignation_date_to or '',
            'contacted_date_from': contacted_date_from or '',
            'contacted_date_to': contacted_date_to or '',
            'search': search or '',
            'sortby': sortby,
            'items_per_page': items_per_page,
        }
        pager = portal_pager(
            url='/my/events',
            url_args=url_args,
            total=event_count,
            page=page,
            step=items_per_page,
        )
        events = event_model.search(
            domain,
            order=sortings[sortby]['order'],
            limit=items_per_page,
            offset=pager['offset'],
        )
        event_rows = self._prepare_event_rows(events)
        page_start = pager['offset'] + 1 if event_count else 0
        page_end = min(pager['offset'] + items_per_page, event_count)

        values = self._prepare_portal_layout_values()
        values.update({
            'accounts': accounts,
            'available_stages': available_stages,
            'available_services': available_services,
            'events': events,
            'event_rows': event_rows,
            'event_count': event_count,
            'page_name': 'client_events',
            'pager': pager,
            'selected_account_id': selected_account_id,
            'account_identifier_label': account_identifier_label,
            'selected_stage_id': selected_stage_id,
            'selected_service_id': selected_service_id,
            'assignation_date_from': assignation_date_from or '',
            'assignation_date_to': assignation_date_to or '',
            'contacted_date_from': contacted_date_from or '',
            'contacted_date_to': contacted_date_to or '',
            'search': search or '',
            'sortby': sortby,
            'sortings': sortings,
            'items_per_page': items_per_page,
            'items_per_page_options': (10, 25, 50, 100),
            'page_start': page_start,
            'page_end': page_end,
        })
        return request.render('ike_event_portal.portal_client_events', values)

    @staticmethod
    def _safe_integer(value):
        try:
            return int(value) if value else False
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _safe_date(value):
        try:
            return fields.Date.to_date(value) if value else False
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _local_date_bound(value, day_time):
        user_timezone = timezone(request.env.user.tz or 'UTC')
        local_datetime = user_timezone.localize(datetime.combine(value, day_time))
        return local_datetime.astimezone(UTC).replace(tzinfo=None)
