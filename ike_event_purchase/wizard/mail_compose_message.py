from odoo import models


class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        """
        Override of `_action_send_mail` to send new values to RFQ at send mail.
        """
        result_mails_su, result_messages = super()._action_send_mail(auto_commit=auto_commit)

        ticket_ids = self.env.context.get('x_sh_helpdesk_ticket_ids') or []
        if ticket_ids:
            # Clean context
            clean_context = self.env.context.copy()
            clean_context['x_sh_helpdesk_ticket_ids'] = None

            ticket_ids = self.env['sh.helpdesk.ticket'].browse(ticket_ids)

            for ticket in ticket_ids:
                for order in ticket.sh_purchase_order_ids:
                    order.with_context(clean_context).x_action_send_new_values_rfq()

        return result_mails_su, result_messages
