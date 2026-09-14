from odoo import models, fields


class CustomProductHomologation(models.Model):
    _name = "custom.product.homologation"
    _description = "help to find product"

    x_ref_sap_api = fields.Char(string="API SAP ref")

    product_id = fields.Many2one(
        'product.product',
        string='',
    )
    description = fields.Char(string='Description')
    event_type_id = fields.Many2one(
        'custom.type.event',
        string='Event Type',
        ondelete='restrict',
    )
    incident_type_id = fields.Many2one(
        'custom.incident.type',
        string='Incident Type',
        ondelete='restrict',
    )
    weight_category_id = fields.Many2one(
        'custom.vehicle.weight.category',
        string='Weight Category',
        ondelete='restrict',
    )
