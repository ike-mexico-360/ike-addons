from odoo import models, api, fields


class ProductProduct(models.Model):
    _inherit = 'product.product'

    standard_price = fields.Float(
        groups="base.group_user,purchase.group_purchase_manager,ike_event_portal.custom_group_portal_finance"
    )

    @api.model
    def get_concepts_uom_ids(self):
        """ Auxiliar para obtener dominio en el portal """
        return self._get_concepts_uom_ids()
