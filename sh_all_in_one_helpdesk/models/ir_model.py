# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, api


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model_create_multi
    def create(self, vals):
        res = super(IrAttachment, self).create(vals)
        for each_record in res:
            if each_record.res_model and each_record.res_id and each_record.res_model == 'sh.helpdesk.ticket':
                helpdesk = self.env['sh.helpdesk.ticket'].browse(each_record.res_id)
                helpdesk.attachment_ids = [(4, each_record.id,0)]
                # each_record.public = True
        return res


class IrModel(models.Model):
    _inherit = 'ir.model.data'

    @api.model
    def xmlid_to_res_model_res_id(self, xmlid, raise_if_not_found=False):
        return self._xmlid_to_res_model_res_id(xmlid, raise_if_not_found)[1]
