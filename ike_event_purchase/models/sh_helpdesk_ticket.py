from odoo import models, _


class ShHelpdeskTicket(models.Model):
    _inherit = 'sh.helpdesk.ticket'

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
                order.x_action_approve_dispute()
                order.x_action_start_consolidation()
        return super().action_done()

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
