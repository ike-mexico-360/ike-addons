from odoo import models


class ProductProduct(models.Model):
    _inherit = 'product.product'

    def get_concepts_uom_ids(self):
        """ Auxiliar para obtener dominio en el portal """
        return self._get_concepts_uom_ids()
