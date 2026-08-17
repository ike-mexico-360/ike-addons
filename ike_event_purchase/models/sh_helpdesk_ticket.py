from odoo import models, fields, api, _


class ShHelpdeskTicket(models.Model):
    _name = 'sh.helpdesk.ticket'
    _inherit = ['sh.helpdesk.ticket', 'mail.tracking.duration.mixin']
    _track_duration_field = 'stage_id'

    current_stage_date = fields.Datetime(compute='_compute_current_stage_tracking')
    current_elapsed_time_seconds = fields.Integer(compute='_compute_current_stage_tracking')
    x_stage_max_wait_time_minutes = fields.Integer(
        related='stage_id.x_max_wait_time_minutes',
    )
    x_event_id = fields.Many2one('ike.event', string='Event', ondelete='set null')
    in_progress_stage_boolean = fields.Boolean(compute='_compute_in_progress_stage_boolean')
    is_done_stage = fields.Boolean(compute='_compute_is_done_stage')

    @api.depends('stage_id')
    def _compute_current_stage_tracking(self):
        tracking_field = self.env['ir.model.fields'].sudo().search_fetch([
            ('model', '=', self._name),
            ('name', '=', self._track_duration_field),
        ], ['id'], limit=1)
        persisted_records = self.filtered(lambda ticket: isinstance(ticket.id, int))
        trackings = []
        if tracking_field and persisted_records:
            self.env.cr.execute("""
                SELECT m.res_id,
                       v.create_date,
                       v.new_value_integer
                  FROM mail_tracking_value v
             LEFT JOIN mail_message m
                    ON m.id = v.mail_message_id
                   AND v.field_id = %(field_id)s
                 WHERE m.model = %(model_name)s
                   AND m.res_id IN %(record_ids)s
              ORDER BY v.id DESC
            """, {
                'field_id': tracking_field.id,
                'model_name': self._name,
                'record_ids': tuple(persisted_records.ids),
            })
            trackings = self.env.cr.dictfetchall()

        now = fields.Datetime.now()
        for ticket in self:
            current_stage_tracking = next((
                tracking for tracking in trackings
                if tracking['res_id'] == ticket.id
                and tracking['new_value_integer'] == ticket.stage_id.id
            ), None)
            ticket.current_stage_date = (
                current_stage_tracking['create_date']
                if current_stage_tracking else ticket.create_date
            )
            ticket.current_elapsed_time_seconds = max(
                int((now - ticket.current_stage_date).total_seconds()), 0
            ) if ticket.current_stage_date else 0

    @api.depends('stage_id')
    def _compute_is_done_stage(self):
        done_stage = self.env.ref('sh_all_in_one_helpdesk.done_stage').id
        for rec in self:
            rec.is_done_stage = rec.stage_id.id == done_stage

    @api.depends('stage_id')
    def _compute_in_progress_stage_boolean(self):
        in_progress_ref = self.env.ref('sh_all_in_one_helpdesk.in_progress_stage').id
        for rec in self:
            rec.in_progress_stage_boolean = rec.stage_id.id == in_progress_ref

    def action_reply(self):
        """ Override of `sh.helpdesk.ticket.action_reply` to send new values to RFQ. """
        res = super().action_reply()
        ctx = res.get('context', {})
        ctx['x_sh_helpdesk_ticket_ids'] = self.ids
        res['context'] = ctx
        return res

    def action_done(self):
        """ Override of `sh.helpdesk.ticket.action_done` to close ticket and apply purchase logic """
        self.ensure_one()
        if self.sh_purchase_order_ids:
            for order in self.sh_purchase_order_ids:
                # Si se cierra desde el portal, se omite este proceso
                # Si se da clic desde el ticket, se ejecutará
                if self._context.get('is_portal', False) is False:
                    order.x_action_approve_dispute()

                order.x_action_start_consolidation()
        res = super().action_done()
        if self.company_id and self.company_id.done_stage_id and self.stage_id != self.company_id.done_stage_id:
            # Update the stage to the 'done_stage_id'
            self.stage_id = self.company_id.done_stage_id.id
        return res

    def sh_check_access(self, vals):
        if self.env.context.get('ike_assignment_wizard'):
            return
        return super().sh_check_access(vals)

    def _sh_auto_assign_user(self, vals):
        if self.env.context.get('ike_assignment_wizard') and vals.get('user_id'):
            return
        return super()._sh_auto_assign_user(vals)

    def x_action_open_purchase_order(self):
        view_id = self.env.ref('ike_event_purchase.purchase_order_helpdesk_dispute_form').id

        if not self.sh_purchase_order_ids:
            return False

        return {
            'name': _('Cost Review'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.sh_purchase_order_ids[0].id,
            'view_mode': 'form',
            'view_id': view_id,
            'target': 'new',
            'context': {
                **self.env.context,
                'create': False,
                'dialog_size': 'extra-large',
            },

        }
