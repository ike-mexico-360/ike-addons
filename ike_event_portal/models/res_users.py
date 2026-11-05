from odoo import fields, models


class ResUsers(models.Model):
    _inherit = 'res.users'

    x_portal_truck_visible_columns = fields.Json(
        string='Portal truck visible columns',
        help='Stores the truck-list columns selected by this portal user.',
        default=False,
        copy=False,
    )

    def x_ike_portal_center_ids(self):
        """Attention Centers the current portal Supervisor is limited to ([] = no limit).
        Used by the record rules; always works on the current user."""
        user = self.env.user
        if (
            not user.has_group('ike_event_portal.custom_group_portal_supervisor')
            or user.has_group('ike_event_portal.custom_group_portal_admin')
        ):
            return []
        return self.env['res.partner.supplier_users.rel'].sudo().search([
            ('user_id', '=', user.id),
        ]).mapped('center_of_attention_id').ids
