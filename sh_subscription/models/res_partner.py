
from odoo import fields, models, api


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_subscription_ids = fields.One2many('sh.subscription.subscription', 'sh_partner_id', 'Afiliaciones')
    x_subscriber_ids = fields.Many2many(
        'res.partner', 'res_partner_account_subscribers_rel', 'account_id', 'subscriber_id', 'Afiliados',
        compute='_compute_x_subscriber_ids')
    x_subscriber_count = fields.Integer(string='Número de afiliados', compute='_compute_x_subscriber_ids')

    # === COMPUTE === #
    def _compute_x_subscriber_ids(self):
        for rec in self:
            x_subscription_ids = self.env["sh.subscription.subscription"].sudo().search([
                ('x_subscription_account_id', '=', rec.id),
                ('state', 'in', ['in_progress', 'renewed'])
            ])
            if x_subscription_ids:
                subscriber_ids = x_subscription_ids.mapped("sh_partner_id").ids
                rec.x_subscriber_ids = subscriber_ids
                rec.x_subscriber_count = len(subscriber_ids)
            else:
                rec.x_subscriber_ids = False
                rec.x_subscriber_count = 0
