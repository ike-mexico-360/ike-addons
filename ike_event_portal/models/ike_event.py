from odoo import models, Command, _


class IkeEvent(models.Model):  # FIXME: OR DELETEME
    _inherit = 'ike.event'

    def test_button_notification(self):
        self.ensure_one()
        self.env['bus.bus']._sendone(
            target='ike_event_notification',
            notification_type='notification',
            message={'text': 'test message'}
        )

    # def action_find_electronic_suppliers(self):
    #     """ Override to capture the electronic suppliers found """
    #     # 1. Run the original logic (this creates/updates the lines)
    #     res = super(IkeEvent, self).action_find_electronic_suppliers()

    #     # 2. Re-capture the suppliers using the same logic as the original method
    #     for rec in self:
    #         electronic_supplier_ids = rec.service_supplier_ids.filtered(
    #             lambda x:
    #                 x.search_number == rec.supplier_search_number
    #                 and x.assignation_type == 'electronic'
    #                 and x.priority == '3'
    #                 and not x.display_type
    #         )

    #         if electronic_supplier_ids:
    #             supplier_names = electronic_supplier_ids.mapped('supplier_id.name')
    #             rec.env['bus.bus']._sendone(
    #                 target='ike_event_notification',
    #                 notification_type='notification',
    #                 message={
    #                     'id': rec.id,
    #                     'supplier': supplier_names[0],
    #                     'supplier_ids': electronic_supplier_ids[0].ids[0]
    #                 }
    #             )

    #     return res

    def _find_electronic_suppliers(self):  # FIXME: OR DELETEME
        """
        Extend the original method.
        1. Call super() to get the original list of commands.
        2. Append your custom logic/suppliers to that list.
        """
        # 1. Get the list from the original implementation
        service_suppliers = super(IkeEvent, self)._find_electronic_suppliers()

        # 2. Add your custom logic here
        # Example: Find a specific "Portal" supplier to add
        portal_suppliers = self.env['res.partner'].search_read(
            [('x_is_supplier', '=', True), ('name', 'ilike', 'Portal')],
            ['id', 'name'],
            limit=1
        )

        if portal_suppliers:
            supplier = portal_suppliers[0]

            service_suppliers.append(Command.create({
                'name': _('Portal Extras'),
                'display_type': 'line_section',
                'assignation_type': 'electronic',
                'state': False,
            }))

            # Add the supplier line
            service_suppliers.append(Command.create({
                'name': f"Portal Added: {supplier['name']}",
                'assignation_type': 'electronic',
                'state': 'available',
                'supplier_id': supplier['id'],
                'ranking': 99,  # High ranking to put at end
                'priority': '3',
                'estimated_duration': 15,
                'estimated_cost': 500.00,
                'timer_duration': 60,
            }))

            # Send notification immediately if needed
            self.env['bus.bus']._sendone(
                target='ike_event_notification',
                notification_type='notification',
                message={
                    'id': self.id,  # Note: self.id might not be available if called during creation
                    'supplier': supplier['name'],
                    'text': 'Extra portal supplier added'
                }
            )

        return service_suppliers

    def action_find_publication_suppliers_3(self):
        self._get_publication_suppliers('3')  # FIXME: OR DELETEME


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
