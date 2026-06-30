from odoo import models


class CustomVehicleImportWizard(models.TransientModel):
    _inherit = 'custom.vehicle.import.wizard'

    def _get_user_group_ids(self, user):
        groups = super()._get_user_group_ids(user)
        # Usuario Operador (Portal)
        portal_operator_group = self.env.ref('ike_event_portal.custom_group_portal_operator', raise_if_not_found=False)
        if portal_operator_group:
            groups.append(portal_operator_group.id)
        return groups
