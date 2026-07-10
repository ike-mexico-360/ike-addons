# -*- coding: utf-8 -*-
from odoo import models, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    def _should_restrict_export(self):
        """
        Helper method to determine if a user should be restricted from exporting.
        Target: Users with the Coordinator group, EXCLUDING higher roles like
        Supervisor CDS and Manager CDS that inherit from it.
        """
        self.ensure_one()
        has_coordinator = self.has_group('custom_master_catalog.custom_group_event_coordinator')
        has_supervisor = self.has_group('custom_master_catalog.custom_group_supervisor_cds')
        has_manager = self.has_group('custom_master_catalog.custom_group_manager_cds')
        has_admin_supplier = self.has_group('custom_master_catalog.custom_group_contact_admin_supplier')
        has_system = self.has_group('base.group_system')

        # Enforce restriction ONLY if they are a Coordinator but NOT a Supervisor or Manager..
        return has_coordinator and not has_supervisor and not has_manager and not has_admin_supplier and not has_system

    @api.model_create_multi
    def create(self, vals_list):
        users = super(ResUsers, self).create(vals_list)
        allow_export_group = self.env.ref('base.group_allow_export', raise_if_not_found=False)

        if allow_export_group:
            for user in users:
                # Apply strict role validation after creation
                if user._should_restrict_export() and user.has_group('base.group_allow_export'):
                    super(ResUsers, user).write({'groups_id': [(3, allow_export_group.id, 0)]})

        return users

    def write(self, vals):
        res = super(ResUsers, self).write(vals)
        allow_export_group = self.env.ref('base.group_allow_export', raise_if_not_found=False)

        if allow_export_group:
            for user in self:
                # Apply strict role validation after update execution
                if user._should_restrict_export() and user.has_group('base.group_allow_export'):
                    super(ResUsers, user).write({'groups_id': [(3, allow_export_group.id, 0)]})

        return res

    @api.model
    def _cron_restrict_coordinator_export_permission(self):
        """
        Scheduled action to search all existing users, evaluate their exact role tree,
        and revoke both the Export and the Event Admin permission groups exclusively for Coordinators.
        """
        coordinator_group = self.env.ref('custom_master_catalog.custom_group_event_coordinator', raise_if_not_found=False)
        allow_export_group = self.env.ref('base.group_allow_export', raise_if_not_found=False)

        # Fetch the Event Admin group to revoke it during the cron execution
        event_admin_group = self.env.ref('ike_event.group_ike_event_admin', raise_if_not_found=False)

        if not coordinator_group:
            return False

        # Target all users belonging to the coordinator group ecosystem due to inheritance
        coordinator_users = self.search([('groups_id', 'in', coordinator_group.id)])

        for user in coordinator_users:
            commands = []

            # 1. Evaluate export restriction condition
            if allow_export_group and user._should_restrict_export() and user.has_group('base.group_allow_export'):
                # Command (3, ID, 0) unlinks the export group
                commands.append((3, allow_export_group.id, 0))

            # 2. Evaluate Event Admin group condition to revoke it for base Coordinators
            if event_admin_group and user.has_group('ike_event.group_ike_event_admin'):
                # Command (3, ID, 0) unlinks the Event Admin group
                commands.append((3, event_admin_group.id, 0))

            if commands:
                super(ResUsers, user).write({'groups_id': commands})

        return True
