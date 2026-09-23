# -*- coding: utf-8 -*-
from odoo import models, fields, api


class IkeEventMembershipAuthorization(models.Model):
    _name = 'ike.event.membership.authorization'
    _description = 'Nus Membership Authorization'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    # === KEY FIELDS === #
    event_id = fields.Many2one('ike.event', ondelete='cascade', required=True)
    nus_membership_id = fields.Many2one('custom.membership.nus', required=True)

    # === FIELDS === #
    # name = fields.Char(related='nus_membership_id.name')
    name = fields.Char(string="name", compute='_compute_name')
    nus_id = fields.Many2one('custom.nus', required=True)
    authorizer_id = fields.Many2one('res.partner', required=True)
    authorization_date = fields.Datetime()
    state = fields.Selection([
        ('pending', 'Pending'),
        ('authorized', 'Authorized'),
        ('rejected', 'Rejected'),
    ], default='pending')

    # COMPUTE
    @api.depends('nus_membership_id.name')
    def _compute_name(self):
        encryption = self.env['custom.model.encryption']
        for rec in self:
            if rec.nus_membership_id and rec.nus_membership_id.name:
                decrypted = encryption.x_decrypt_aes256(
                    rec.nus_membership_id.name
                )
                rec.name = decrypted or False
            else:
                rec.name = False
