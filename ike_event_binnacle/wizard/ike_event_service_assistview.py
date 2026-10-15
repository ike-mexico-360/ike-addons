from odoo import models


class IkeEventServiceAssistView(models.TransientModel):
    _inherit = 'ike.event.service.assistview'

    def write(self, vals):
        to_notify = self.env['ike.event.service.assistview']
        if vals.get('received_assistview'):
            to_notify = self.filtered(lambda x: not x.received_assistview)

        res = super().write(vals)

        for rec in to_notify:
            rec.event_id._create_message_binnacle([
                'ike_event_binnacle.ike_binnacle_received_assistview'
            ])

        return res
