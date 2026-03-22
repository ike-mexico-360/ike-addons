
from odoo import api, models, fields, _


class CustomModelConfirmWizard(models.TransientModel):
    """Create a confirm wizard with reason text.

        :param res_model (str): comodel_name
        :param res_ids (str): list of ids in a string like [1,2,3]
        :param action_name (str): action to execute
        :param reason (str): text reason
        :return Executes an Action: passed by action_name param
    """
    _name = 'custom.model.confirm.wizard'
    _description = 'Custom model confirm wizard'

    res_model = fields.Char('Model', required=True)
    res_ids = fields.Char('References', required=True)
    action_name = fields.Char('Action', required=True)
    reason = fields.Text()

    def action_confirm(self):
        self.ensure_one()
        MODEL = self.env[self.res_model]
        if getattr(MODEL, self.action_name, None):
            res_ids = [int(x) for x in self.res_ids[1:-1].split(',')]
            rec_ids = MODEL.browse(res_ids)
            method = getattr(rec_ids, self.action_name, None)
            if callable(method):
                method(self.reason)

        return {'type': 'ir.actions.act_window_close'}
