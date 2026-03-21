from odoo import models, fields


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    # Link to ike.event.supplier.product, if not value, has manual cost
    x_supplier_product_id = fields.Many2one('ike.event.supplier.product', 'Supplier Product')

    # Dispute
    x_price_unit_dispute = fields.Float('Dispute Price')
    x_product_qty_dispute = fields.Float('Dispute Quantity')
    # Approved
    x_price_unit_approved = fields.Float('Approved Price')
    x_product_qty_approved = fields.Float('Approved Quantity')
