# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsersApiKeys(models.Model):
    _inherit = 'res.users.apikeys'

    x_service_api = fields.Char(string="Servicio API")

    def init(self):
        super().init()
        # By having _auto = False in the base model, we force the creation of the field:
        self.env.cr.execute("""
            ALTER TABLE res_users_apikeys
            ADD COLUMN IF NOT EXISTS x_service_api VARCHAR;
        """)
