# -*- coding: utf-8 -*-

from odoo import models, fields, api


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
            ('stage_ref', '=', 'verifying')
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
                    ('stage_ref', '=', 'verifying'),
                    ('assigned_user_id', 'in', rec.assigned_user_ids.ids)
                ])
            else:
                rec.event_assign_ids = False

    def action_assignment_event(self):
        if not self.assigned_user_id:
            return

        self.event_not_assign_ids.write({
            'assigned_user_id': self.assigned_user_id.id
        })
