from odoo import models, fields


class CustomMembershipNus(models.Model):
    _inherit = 'custom.membership.nus'

    # integración con servidor externo
    x_service_counter_validation = fields.Boolean(
        string='Service counter validation', default=False,
        help="Flag to determine whether the counters in service will be queried on the endpoint defined in the coverage plan")
