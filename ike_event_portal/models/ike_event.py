from odoo import models, Command, fields, _


class ResPartnerSupplierDriversRel(models.Model):
    _inherit = 'res.partner.supplier_drivers.rel'

    def _x_ike_get_operator_groups(self):
        portal_group = super()._x_ike_get_operator_groups()
        portal_group.extend([
            self.env.ref('ike_event_portal.custom_group_portal_operator').id,
            self.env.ref('ike_event_portal.custom_group_portal_supervisor').id,
            self.env.ref('ike_event_portal.custom_group_portal_admin').id
        ])
        return portal_group


class ResPartnerSupplierUserssRel(models.Model):
    _inherit = 'res.partner.supplier_users.rel'

    def _x_ike_get_operator_groups(self):
        portal_group = super()._x_ike_get_operator_groups()
        portal_group.extend([
            self.env.ref('ike_event_portal.custom_group_portal_operator').id,
            self.env.ref('ike_event_portal.custom_group_portal_supervisor').id,
            self.env.ref('ike_event_portal.custom_group_portal_admin').id
        ])
        return portal_group
