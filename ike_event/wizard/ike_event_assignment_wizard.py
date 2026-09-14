# -*- coding: utf-8 -*-

from odoo import models, fields, api


ACTIVE_CDS_STAGE_REFS = (
    'draft',
    'capturing',
    'searching',
    'assigned',
    'in_progress',
)


class IkeEventAssignmentWizard(models.TransientModel):
    _name = "ike.event.assignment.wizard"
    _description = "Assignment event wizard"

    assigned_user_ids = fields.Many2many('res.users', string='Assigned to users')
    assigned_user_id = fields.Many2one('res.users', string='Assigned to user')
    assigned_user_domain = fields.Binary(compute='_compute_assigned_user_domain')
    event_not_assign_ids = fields.Many2many(
        'ike.event',
        'ike_event_assignment_wizard_not_assign_rel',
        'wizard_id',
        'event_id',
        string='Events not assigned',
        domain=[
            ('assigned_user_id', '=', False),
            ('stage_ref', 'in', ['verifying', 'cancel_verifying']),
        ]
    )
    event_assign_ids = fields.Many2many(
        'ike.event',
        'ike_event_assignment_wizard_assign_rel',
        'wizard_id',
        'event_id',
        string='Events to assign',
        compute='_compute_event_assign_ids'
    )
    reassigned_user_id = fields.Many2one(
        'res.users',
        string='Reassign to user',
    )
    event_reassignment_ids = fields.Many2many(
        'ike.event',
        'ike_event_assignment_wizard_reassign_rel',
        'wizard_id',
        'event_id',
        string='Events to reassign',
    )

    # === COMPUTES === #
    @api.depends('assigned_user_ids', 'assigned_user_id')
    def _compute_assigned_user_domain(self):
        for rec in self:
            domain = [
                ('active', '=', True),
                ('groups_id', 'in', [
                    self.env.ref('custom_master_catalog.custom_group_ccc_coordinator').id,
                    self.env.ref('custom_master_catalog.custom_group_ccc_analyst').id,
                    self.env.ref('custom_master_catalog.custom_group_ccc_boss').id,
                ])
            ]

            rec.assigned_user_domain = domain

    @api.depends('assigned_user_ids')
    def _compute_event_assign_ids(self):
        for rec in self:
            if rec.assigned_user_ids:
                rec.event_assign_ids = self.env['ike.event'].search([
                    ('stage_ref', 'in', ['verifying', 'cancel_verifying']),
                    ('assigned_user_id', 'in', rec.assigned_user_ids.ids)
                ])
            else:
                rec.event_assign_ids = False

    def action_assignment_event(self):
        if self.reassigned_user_id and self.event_reassignment_ids:
            return self.action_reassignment_event()

        if not self.assigned_user_id:
            return

        self.event_not_assign_ids.write({
            'assigned_user_id': self.assigned_user_id.id
        })

    def action_reassignment_event(self):
        if not self.reassigned_user_id:
            return

        eligible_events = self.event_reassignment_ids.filtered(
            lambda event: event.assigned_user_id
            and event.assigned_user_id != self.env.user
            and event.stage_ref in ('verifying', 'cancel_verifying')
        )
        eligible_events.write({
            'assigned_user_id': self.reassigned_user_id.id,
        })


class CustomEventAssignmentCdsWizard(models.TransientModel):
    _name = 'custom.event.assignment.cds.wizard'
    _description = 'CDS Event Assignment Wizard'

    assigned_user_ids = fields.Many2many(
        'res.users',
        'custom_event_assignment_cds_wizard_res_users_rel',
        'wizard_id',
        'user_id',
        string='Assigned to users',
    )
    assigned_user_id = fields.Many2one('res.users', string='Assigned to user')
    assigned_user_domain = fields.Binary(compute='_compute_assigned_user_domain')
    event_not_assign_ids = fields.Many2many(
        'ike.event',
        'custom_event_assignment_cds_wizard_ike_event_not_rel',
        'wizard_id',
        'event_id',
        string='Events not assigned',
        domain=[
            ('assigned_user_id', '=', False),
            ('stage_ref', 'in', ACTIVE_CDS_STAGE_REFS),
        ],
    )
    event_assign_ids = fields.Many2many(
        'ike.event',
        'custom_event_assignment_cds_wizard_ike_event_rel',
        'wizard_id',
        'event_id',
        string='Events to assign',
        compute='_compute_event_assign_ids',
    )
    reassigned_user_id = fields.Many2one(
        'res.users',
        string='Reassign to user',
    )
    event_reassignment_ids = fields.Many2many(
        'ike.event',
        'custom_event_assignment_cds_wizard_ike_event_reassign_rel',
        'wizard_id',
        'event_id',
        string='Events to reassign',
    )

    @api.depends('assigned_user_ids', 'assigned_user_id')
    def _compute_assigned_user_domain(self):
        coordinator_group = self.env.ref(
            'custom_master_catalog.custom_group_event_coordinator'
        )
        for record in self:
            record.assigned_user_domain = [
                ('active', '=', True),
                ('groups_id', 'in', coordinator_group.ids),
            ]

    @api.depends('assigned_user_ids')
    def _compute_event_assign_ids(self):
        for record in self:
            if record.assigned_user_ids:
                record.event_assign_ids = self.env['ike.event'].search([
                    ('stage_ref', 'in', ACTIVE_CDS_STAGE_REFS),
                    ('assigned_user_id', 'in', record.assigned_user_ids.ids),
                ])
            else:
                record.event_assign_ids = False

    def action_assignment_event(self):
        if self.reassigned_user_id and self.event_reassignment_ids:
            return self.action_reassignment_event()

        if self.assigned_user_id:
            eligible_events = self.event_not_assign_ids.filtered(
                lambda event: not event.assigned_user_id
                and event.stage_ref in ACTIVE_CDS_STAGE_REFS
            )
            eligible_events.write({
                'assigned_user_id': self.assigned_user_id.id,
            })

    def action_reassignment_event(self):
        if not self.reassigned_user_id:
            return

        eligible_events = self.event_reassignment_ids.filtered(
            lambda event: event.assigned_user_id
            and event.assigned_user_id != self.env.user
            and event.stage_ref in ACTIVE_CDS_STAGE_REFS
        )
        eligible_events.write({
            'assigned_user_id': self.reassigned_user_id.id,
        })
