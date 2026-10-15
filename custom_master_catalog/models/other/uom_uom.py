from odoo import models


class UomUom(models.Model):
    _inherit = 'uom.uom'

    def _x_get_ike_service_uom_id(self):
        return self.env.ref('uom.product_uom_unit')
