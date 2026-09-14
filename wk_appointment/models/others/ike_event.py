from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from datetime import timedelta
import logging


class IkeEvent(models.Model):
    _inherit = 'ike.event'

    appointment_wait_time = fields.Integer(
        readonly=True,
        copy=False,
    )
    appointment_min_date = fields.Datetime(
        string='Min event date',
        copy=False
    )

    events_display_wait_time = fields.Integer(
        readonly=True,
        copy=False,
    )
    appointment_show_event_date = fields.Datetime(
        string="Display event date"
    )

    # ==== ONCHANGE ==== #
    @api.onchange('scheduled')
    def onchange_scheduled(self):
        if self.scheduled:
            base_date = fields.Datetime.now()
            self.appointment_min_date = base_date + timedelta(minutes=self.appointment_wait_time)
            self.event_date = self.appointment_min_date

    @api.onchange('event_date')
    def onchange_event_date(self):
        if self.event_date and self.appointment_min_date and self.event_date < self.appointment_min_date:
            self.event_date = False
            local_min_date = fields.Datetime.context_timestamp(self, self.appointment_min_date)
            return {
                'warning': {
                    'title': _('Invalid date'),
                    'message': _(
                        'The event date cannot be earlier than the minimum appointment date (%s).'
                    ) % local_min_date.strftime('%Y-%m-%d %H:%M:%S'),
                }
            }

    # ==== FUNCTION ==== #
    def _get_appointment_wait_time(self):
        return int(
            self.env['ir.config_parameter'].sudo().get_param(
                'wk_appointment.appointment_wait_time',
                default=0,
            )
        )

    def _get_appointment_wait_to_show_event(self):
        return int(
            self.env['ir.config_parameter'].sudo().get_param(
                'wk_appointment.events_display_wait_time',
                default=0,
            )
        )

    # ==== ACTIONS ==== #
    def action_set_service_data(self):
        result = super().action_set_service_data()

        for rec in self:
            if rec.scheduled and rec.event_date:
                rec.appointment_show_event_date = rec.event_date - timedelta(
                    minutes=rec.events_display_wait_time or 0
                )

        return result

    def action_auto_assign_event(self):
        self.assigned_user_id = self.env.user.id

    def action_change_normal_event(self):
        self.scheduled = False
        self.event_date = fields.Datetime.now()
        self.selected_supplier_ids.truck_id.x_vehicle_service_state = 'available'
        self.selected_supplier_ids.broadcastCancelForSupplier()
        self.event_summary_id.set_service_data()

    def action_open_change_to_appointment_view(self):
        self.ensure_one()

        if self.stage_ref != 'assigned':
            raise UserError(
                _('Only assigned events can be changed to an appointment.')
            )

        view = self.env.ref(
            'wk_appointment.ike_event_screen_form_change_appointment_views'
        )

        return {
            'name': _('Schedule Event'),
            'type': 'ir.actions.act_window',
            'res_model': 'ike.event',
            'res_id': self.id,
            'views': [(view.id, 'form')],
            'view_mode': 'form',
            'target': 'new',
        }

    def action_change_to_appointment(self):
        self.ensure_one()

        display_wait_time = (self._get_appointment_wait_to_show_event())
        wait_time = self._get_appointment_wait_time()
        min_date = fields.Datetime.now() + timedelta(
            minutes=wait_time
        )

        if self.event_date < min_date:
            local_min_date = fields.Datetime.context_timestamp(self, min_date)

            raise ValidationError(
                _(
                    'The event date must be on or after %s.',
                    local_min_date.strftime('%d/%m/%Y %H:%M:%S'),
                )
            )

        self.write({
            'scheduled': True,  # type: ignore
            'event_date': self.event_date,
            'appointment_wait_time': wait_time,
            'appointment_min_date': min_date,
            'events_display_wait_time': display_wait_time,
            'appointment_show_event_date': (
                self.event_date
                - timedelta(minutes=display_wait_time)
            ),
        })
        # CHANGE STATE VEHICLE
        self.selected_supplier_ids.truck_id.x_vehicle_service_state = 'available'

        self.action_notify_changed_to_scheduled()
        return {'type': 'ir.actions.act_window_close'}

    # ==== CRUD ==== #
    @api.model_create_multi
    def create(self, vals_list):
        wait_time = self._get_appointment_wait_time()
        wait_display_event = self._get_appointment_wait_to_show_event()
        for vals in vals_list:
            vals.setdefault('appointment_wait_time', wait_time)
            vals.setdefault('events_display_wait_time', wait_display_event)
        return super().create(vals_list)
