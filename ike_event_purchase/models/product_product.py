from odoo import models, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def get_concepts_uom_ids(self):
        """ Auxiliar para obtener dominio en el portal """
        return self._get_concepts_uom_ids()
