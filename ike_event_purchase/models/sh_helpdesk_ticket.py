from odoo import models, _


class ShHelpdeskTicket(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    def action_reply(self):
        res = super().action_reply()
        for rec in self:
            if rec.sh_purchase_order_ids:
                for order in rec.sh_purchase_order_ids:
                    order.x_action_send_new_values_rfq()
        return res

    def x_action_open_purchase_order(self):
        return {
            'name': _('Purchase Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.sh_purchase_order_ids[0].id,
            'view_mode': 'form',
            'target': 'new',
            'context': {
                **self.env.context,
                'create': False,
                'dialog_size': 'extra-large',
            },
        }
