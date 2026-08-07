from odoo import models, fields


class IkeEventConfirmCostsWizard(models.TransientModel):
    _name = 'ike.event.confirm.costs.wizard'
    _description = 'Cost Confirmation Wizard'

    event_id = fields.Many2one('ike.event', string='Event', required=True)

    def action_confirm(self):
        self.ensure_one()
        return self.event_id.sudo().action_close()

    def action_cancel(self):
        return {'type': 'ir.actions.act_window_close'}