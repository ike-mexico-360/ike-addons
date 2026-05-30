from odoo import models, fields, api, _


class ShHelpdeskTicket(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    x_event_id = fields.Many2one('ike.event', string='Event', ondelete='set null')
    in_progress_stage_boolean = fields.Boolean(compute='_compute_in_progress_stage_boolean')

    @api.depends('stage_id')
    def _compute_in_progress_stage_boolean(self):
        in_progress_ref = self.env.ref('sh_all_in_one_helpdesk.in_progress_stage').id
        for rec in self:
            rec.in_progress_stage_boolean = rec.stage_id.id == in_progress_ref

    def action_reply(self):
        """ Override of `sh.helpdesk.ticket.action_reply` to send new values to RFQ. """
        res = super().action_reply()
        for rec in self:
            if rec.sh_purchase_order_ids:
                for order in rec.sh_purchase_order_ids:
                    order.x_action_send_new_values_rfq()
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
