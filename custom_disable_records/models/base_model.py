# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    # === FIELDS === #
    can_be_disabled = fields.Boolean(compute='_compute_can_be_disabled')

    # === COMPUTES === #
    @api.model
    def get_can_be_disabled(self):
        return True

    def _compute_can_be_disabled(self):
        self.can_be_disabled = self.get_can_be_disabled()

    # === ACTIONS === #
    def toggle_disable(self):
        "Inverses the value of :attr:`disabled` on the records in ``self``."
        active_recs = self.filtered(lambda record: record['disabled'])
        active_recs['disabled'] = False
        (self - active_recs)['disabled'] = True

    def action_enable(self, reason=None):
        """Sets :attr:`disabled` to ``False`` on a recordset, by calling
         :meth:`toggle_disable` on its currently disabled records.
        """
        return self.filtered(lambda record: record['disabled']).toggle_disable()

    def action_disable(self, reason=None):
        """Sets :attr:`disabled` to ``True`` on a recordset, by calling
        :meth:`toggle_disable` on its currently enabled records.
        """
        return self.filtered(lambda record: not record['disabled']).toggle_disable()
