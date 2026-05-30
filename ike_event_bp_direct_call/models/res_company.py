from odoo import models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    @api.model
    def x_get_bp_tenant(self):
        return self.env["ir.config_parameter"].sudo().get_param("ike_event.bp_tenant", "")

    @api.model
    def x_get_bp_default_service(self):
        return self.env["ir.config_parameter"].sudo().get_param("ike_event.bp_default_service", "")
