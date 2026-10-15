from odoo import models


class ProductProduct(models.Model):
    _inherit = 'uom.uom'

    def _x_get_ike_service_uom_id(self):
        """ Override _x_get_ike_service_uom_id to return the correct l10n_mx Service uom.uom """
        return self.env.ref('l10n_mx.product_uom_service_unit')
