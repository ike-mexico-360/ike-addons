import base64
import secrets
from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    x_current_event_info = fields.Json(compute='_compute_current_event_info')

    # These fields retain the auditable result of a permanent deregistration.
    # The operational plate/economic number are cleared only after the code is
    # validated, so they can be reused by a later service vehicle.
    x_deregistration_evidence_ids = fields.Many2many(
        'ir.attachment', 'fleet_vehicle_deregistration_attachment_rel',
        'vehicle_id', 'attachment_id', string='Permanent deregistration evidence', copy=False,
    )
    x_deregistration_date = fields.Datetime(string='Permanently deregistered on', tracking=True, copy=False)
    x_deregistration_user_id = fields.Many2one('res.users', string='Permanently deregistered by', tracking=True, copy=False)
    x_deregistration_license_plate = fields.Char(string='Deregistered license plate', readonly=True, copy=False)
    x_deregistration_economic_number = fields.Char(string='Deregistered economic number', readonly=True, copy=False)
    x_deregistration_code = fields.Char(string='Deregistration verification code', copy=False, groups='base.group_system')
    x_deregistration_code_expiration = fields.Datetime(string='Deregistration code expiration', copy=False, groups='base.group_system')
    x_deregistration_code_attempts = fields.Integer(string='Deregistration code attempts', default=0, copy=False, groups='base.group_system')
    x_deregistration_requested_by_id = fields.Many2one('res.users', string='Deregistration requested by', copy=False, groups='base.group_system')
    x_not_available_reason = fields.Char(string='Temporary unavailability reason', tracking=True, copy=False)
    x_not_available_return_date = fields.Date(string='Estimated return date', tracking=True, copy=False)

    def write(self, values):
        """A permanently deregistered vehicle is irreversible from every entry point."""
        if 'x_vehicle_service_state' in values and not self.env.context.get('allow_deregistration_write'):
            restored = self.filtered(lambda vehicle: vehicle.x_vehicle_service_state == 'deregistration'
                                     and values['x_vehicle_service_state'] != 'deregistration')
            if restored:
                raise UserError(_('A permanently deregistered unit cannot be reactivated.'))
        return super().write(values)

    def _permanent_deregistration_reason_name(self):
        """Return the label of the reason stored in the select field."""
        self.ensure_one()
        reasons = dict(self._fields['x_reason_permanent_deregistration']._description_selection(self.env))
        return reasons.get(self.x_reason_permanent_deregistration, '')

    @api.model
    def _cron_expire_deregistration_codes(self):
        """Cancel expired requests and notify their requester without waiting for an action."""
        expired = self.sudo().search([
            ('x_deregistration_code', '!=', False),
            ('x_deregistration_code_expiration', '<', fields.Datetime.now()),
        ])
        for vehicle in expired:
            requester = vehicle.x_deregistration_requested_by_id
            vehicle.with_context(allow_deregistration_write=True).write({
                'x_deregistration_code': False,
                'x_deregistration_code_expiration': False,
                'x_deregistration_code_attempts': 0,
                'x_deregistration_requested_by_id': False,
            })
            if requester:
                vehicle._portal_deregistration_notify(
                    requester,
                    _('Permanent deregistration was not completed'),
                    _('Permanent deregistration was not completed because the verification code expired.'),
                )

    def _portal_deregistration_events(self):
        """Return blocking and warning events for the permanent-deregistration flow."""
        self.ensure_one()
        lines = self.env['ike.event.supplier'].sudo().search([('truck_id', '=', self.id)])
        # A vehicle can have old events whose event header still says Assigned.
        # Only an open supplier line represents work that is actually assigned
        # to this unit and must block its permanent deregistration.
        open_lines = lines.filtered(
            lambda line: line.state == 'assigned'
            and line.stage_id.ref not in ('finalized', 'cancel')
        )
        blocking = open_lines.mapped('event_id').filtered(
            lambda event: event.stage_id.ref in ('assigned', 'in_progress')
        )
        warnings = lines.mapped('event_id').filtered(
            lambda event: event.stage_id.ref in ('completed', 'verifying')
        )
        return blocking, warnings

    def portal_deregistration_check(self):
        """Business validation shared by the portal request and confirmation APIs."""
        self.ensure_one()
        if self.x_vehicle_service_state not in ('not_available', 'disabled'):
            raise UserError(_('Only unavailable or disabled units can be permanently deregistered.'))
        blocking, warnings = self._portal_deregistration_events()
        if blocking:
            raise UserError(_('The unit cannot be permanently deregistered because it has events in Assigned or In Progress: %s') % ', '.join(blocking.mapped('name')))
        active_same_type = self.search_count([
            ('id', '!=', self.id),
            ('x_partner_id', '=', self.x_partner_id.id),
            ('x_center_id', '=', self.x_center_id.id),
            ('x_vehicle_type', '=', self.x_vehicle_type.id),
            ('x_vehicle_service_state', '!=', 'deregistration'),
        ])
        return {
            'warning_events': warnings.mapped('name'),
            'is_last_unit_of_type': not active_same_type,
        }

    def _portal_deregistration_admins(self):
        self.ensure_one()
        relations = self.env['res.partner.supplier_users.rel'].sudo().search([
            ('supplier_id', '=', self.x_partner_id.id),
        ])
        return relations.mapped('user_id').filtered(
            lambda user: user.has_group('ike_event_portal.custom_group_portal_admin')
        )

    def _portal_deregistration_notify(self, users, subject, body):
        """Deliver both an inbox notification and an email, independently of preferences."""
        partners = users.mapped('partner_id')
        self.message_post(body=body, partner_ids=partners.ids, message_type='notification')
        for partner in partners.filtered('email'):
            self.env['mail.mail'].sudo().create({
                'subject': subject, 'body_html': '<p>%s</p>' % body,
                'email_to': partner.email,
            }).send()

    def portal_request_deregistration_code(self, user, reason, evidence):
        """Store the first confirmation and notify the requesting portal admin."""
        self.ensure_one()
        validation = self.portal_deregistration_check()
        reason_key = str(reason or '')
        reason_keys = dict(self._fields['x_reason_permanent_deregistration']._description_selection(self.env))
        if reason_key not in reason_keys:
            raise UserError(_('Select a valid reason for permanent deregistration.'))
        evidence_files = evidence if isinstance(evidence, list) else [evidence]
        if not evidence_files or not all(file and file.get('data') and file.get('name') for file in evidence_files):
            raise UserError(_('Evidence is required for permanent deregistration.'))
        if len(evidence_files) > 4:
            raise UserError(_('At most 4 evidence files can be attached.'))

        attachments = self.env['ir.attachment']
        max_evidence_size = 3 * 1024 * 1024
        for evidence_file in evidence_files:
            try:
                content = base64.b64decode(evidence_file['data'])
            except (ValueError, TypeError):
                raise UserError(_('The evidence file could not be read.'))
            if not content:
                raise UserError(_('The evidence file is empty.'))
            if len(content) > max_evidence_size:
                raise UserError(_('Evidence file %s exceeds the 3 MB limit.') % evidence_file['name'])
            attachments |= self.env['ir.attachment'].sudo().create({
                'name': evidence_file['name'],
                'datas': evidence_file['data'],
                'mimetype': evidence_file.get('mimetype') or 'application/octet-stream',
                'res_model': self._name,
                'res_id': self.id,
            })
        code = '%06d' % secrets.randbelow(1000000)
        expiration = fields.Datetime.now() + timedelta(minutes=10)
        self.sudo().write({
            'x_reason_permanent_deregistration': reason_key,
            'x_deregistration_evidence_ids': [(6, 0, attachments.ids)],
            'x_deregistration_code': code,
            'x_deregistration_code_expiration': expiration,
            'x_deregistration_code_attempts': 0,
            'x_deregistration_requested_by_id': user.id,
        })
        body = Markup('<p>%s</p><p><b>%s</b> %s</p><p>%s</p>') % (
            _('Permanent deregistration verification requested.'),
            _('Verification code:'), code,
            _('This code expires in 10 minutes.'),
        )
        self._portal_deregistration_notify(user, _('Permanent deregistration verification code'), body)
        return validation

    def portal_confirm_deregistration(self, user, code):
        """Execute an irreversible permanent deregistration after code validation."""
        self.ensure_one()
        self.portal_deregistration_check()
        now = fields.Datetime.now()
        if (not self.x_deregistration_code or self.x_deregistration_requested_by_id != user
                or not self.x_deregistration_code_expiration
                or self.x_deregistration_code_expiration < now):
            self.sudo().write({
                'x_deregistration_code': False,
                'x_deregistration_code_expiration': False,
                'x_deregistration_code_attempts': 0,
                'x_deregistration_requested_by_id': False,
            })
            # The cron normally expires the request first.  This also covers
            # the race where the user submits a code immediately after expiry.
            self._portal_deregistration_notify(
                user,
                _('Permanent deregistration was not completed'),
                _('Permanent deregistration was not completed because the verification code expired.'),
            )
            raise UserError(_('The verification code expired. Request a new code to continue.'))
        if str(code or '').strip() != self.x_deregistration_code:
            attempts = self.x_deregistration_code_attempts + 1
            values = {'x_deregistration_code_attempts': attempts}
            if attempts >= 3:
                values.update({
                    'x_deregistration_code': False,
                    'x_deregistration_code_expiration': False,
                    'x_deregistration_requested_by_id': False,
                })
            self.sudo().write(values)
            if attempts >= 3:
                self._portal_deregistration_notify(user, _('Permanent deregistration was not completed'), _('Permanent deregistration was not completed because the verification attempts were exhausted.'))
                raise UserError(_('The verification attempts were exhausted. Request a new code to continue.'))
            raise UserError(_('Incorrect verification code. You have %s attempt(s) remaining.') % (3 - attempts))

        plate, economic_number = self.license_plate, self.x_economic_number
        admins = self._portal_deregistration_admins()
        self.sudo().write({
            'x_vehicle_service_state': 'deregistration',
            'x_deregistration_date': now,
            'x_deregistration_user_id': user.id,
            'x_deregistration_license_plate': plate,
            'x_deregistration_economic_number': economic_number,
            'x_deregistration_code': False,
            'x_deregistration_code_expiration': False,
            'x_deregistration_code_attempts': 0,
            'x_deregistration_requested_by_id': False,
            'driver_id': False,
            'license_plate': False,
            'x_economic_number': False,
            'disabled': True,
        })
        body = Markup('<p><b>%s</b></p><ul><li>%s %s</li><li>%s %s</li><li>%s %s</li><li>%s %s</li><li>%s %s</li></ul>') % (
            _('Permanent deregistration completed.'),
            _('License plate:'), plate or '',
            _('Economic number:'), economic_number or '',
            _('Reason:'), self._permanent_deregistration_reason_name(),
            _('Date:'), fields.Datetime.to_string(now),
            _('User:'), user.name,
        )
        self._portal_deregistration_notify(admins, _('Permanent deregistration completed'), body)

    def portal_cancel_deregistration(self, user):
        self.ensure_one()
        if self.x_deregistration_requested_by_id != user:
            raise UserError(_('Only the user who requested the deregistration can cancel it.'))
        self.sudo().write({'x_deregistration_code': False, 'x_deregistration_code_expiration': False, 'x_deregistration_code_attempts': 0, 'x_deregistration_requested_by_id': False})
        self._portal_deregistration_notify(user, _('Permanent deregistration was not completed'), _('Permanent deregistration request was cancelled.'))

    def _compute_current_event_info(self):
        """Latest assigned/in-progress event where the truck is assigned on a supplier line that is still open:
        {'id': supplier line id, 'vehicle_id', 'event_id', 'event_name', 'stage_name'} or False."""
        self.x_current_event_info = False
        vehicle_ids = tuple(self._origin.ids)
        if not vehicle_ids:
            return

        query = """
            SELECT DISTINCT ON (es.truck_id)
                es.id
                ,es.truck_id AS vehicle_id
                ,e.id AS event_id
                ,e.name AS event_name
            FROM ike_event_supplier es
            INNER JOIN ike_event e ON e.id = es.event_id
            LEFT JOIN ike_service_stage ss ON ss.id = es.stage_id
            WHERE es.truck_id IN %(vehicle_ids)s
                AND es.state = 'assigned'
                AND e.stage_id IN %(stage_ids)s
                AND (ss.ref IS NULL OR ss.ref NOT IN ('finalized', 'cancel'))
            ORDER BY
                es.truck_id, e.id DESC
        """
        params = {
            "vehicle_ids": vehicle_ids,
            # The truck goes in_service on assignment, while the event is still "Assigned";
            # it only moves to "In Progress" once the supplier is on route.
            "stage_ids": (
                self.env.ref('ike_event.ike_event_stage_assigned').id,
                self.env.ref('ike_event.ike_event_stage_in_progress').id,
            ),
        }
        self.env.cr.execute(query, params)
        result = {row['vehicle_id']: row for row in self.env.cr.dictfetchall()}

        # Stage name through the ORM so it comes translated in the current language.
        supplier_lines = self.env['ike.event.supplier'].sudo().browse([row['id'] for row in result.values()])
        stage_names = {line.id: line.stage_id.name or '' for line in supplier_lines}

        for rec in self:
            data = result.get(rec._origin.id)
            if data:
                rec.x_current_event_info = dict(data, stage_name=stage_names.get(data['id'], ''))
