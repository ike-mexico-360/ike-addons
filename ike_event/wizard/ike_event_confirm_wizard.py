
from odoo import api, models, fields, _


class IkeEventConfirmWizard(models.TransientModel):
    _name = 'ike.event.confirm.wizard'
    _inherit = ['custom.model.confirm.wizard']
    _description = 'Event Confirm Wizard'

    cancel_reason_id = fields.Many2one('ike.event.cancellation.reason', 'Cancel Reason')

    def action_confirm(self):
        self.ensure_one()
        MODEL = self.env[self.res_model]
        if getattr(MODEL, self.action_name, None):
            res_ids = [int(x) for x in self.res_ids[1:-1].split(',')]
            rec_ids = MODEL.browse(res_ids)
            method = getattr(rec_ids, self.action_name, None)
            if callable(method):
                # Cancellation
                if self.env.context.get('ike_event_supplier_cancel') or self.env.context.get('ike_event_cancel'):
                    method(self.cancel_reason_id.id, self.reason)
                # Finalize
                if self.env.context.get('ike_event_supplier_finalize'):
                    method(self.reason)

        return {'type': 'ir.actions.act_window_close'}
