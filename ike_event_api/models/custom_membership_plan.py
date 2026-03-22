from odoo import models, fields


class CustomMembershipPlan(models.Model):
    _inherit = 'custom.membership.plan'

    # Servicio externo de totalizadores
    x_event_totalizer_endpoint_url = fields.Char(
        string="Event totalizer endpoint URL",
        help="Endpoint URL where the sub-service totals for external service membership are queried")
