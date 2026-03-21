# -*- coding: utf-8 -*-
# Copyright 2025 Sveltware Solutions

from odoo import fields, models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    bk_web_icon = fields.Char(readonly=True)

    def u_open_detail(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ir.ui.menu',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [[self.env.ref('udoo_om_ux.om_edit_menu_form').id, 'form']],
        }

    def u_reset_icon(self):
        for rec in self:
            if rec.bk_web_icon:
                rec.write({'web_icon': rec.bk_web_icon, 'bk_web_icon': False})

    def write(self, values):
        if 'web_icon' in values and 'bk_web_icon' not in values:
            for rec in self:
                if rec.web_icon and not rec.bk_web_icon:
                    rec.bk_web_icon = rec.web_icon
        return super().write(values)
