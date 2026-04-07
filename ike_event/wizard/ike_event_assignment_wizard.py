# -*- coding: utf-8 -*-

from odoo import models, fields, api


class IkeEventAssignmentWizard(models.TransientModel):
    _name = "ike.event.assignment.wizard"
    _description = "Assignment event wizard"

    ike_event_coordinator_ids = fields.Many2many('res.users', string='Assigned to')
    ike_event_coordinator_id = fields.Many2one('res.users', string='Assigned to')
    coordinator_domain = fields.Binary(compute='_compute_coordinator_domain')
    event_not_assign_ids = fields.Many2many(
        'ike.event',
        'ike_event_assignment_wizard_not_assign_rel',
        'wizard_id',
        'event_id',
        string='Events not assigned',
        domain=[
            ('ike_event_coordinator_id', '=', False),
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
    @api.depends('ike_event_coordinator_ids', 'ike_event_coordinator_id')
    def _compute_coordinator_domain(self):
        for rec in self:
            domain = [
                ('active', '=', True),
                ('groups_id', 'in', [
                    self.env.ref('custom_master_catalog.custom_group_ccc_coordinator').id,
                    self.env.ref('custom_master_catalog.custom_group_ccc_analyst').id,
                    self.env.ref('custom_master_catalog.custom_group_ccc_boss').id,
                ])
            ]

            rec.coordinator_domain = domain

    @api.depends('ike_event_coordinator_ids')
    def _compute_event_assign_ids(self):
        for rec in self:
            if rec.ike_event_coordinator_ids:
                rec.event_assign_ids = self.env['ike.event'].search([
                    ('stage_ref', '=', 'verifying'),
                    ('ike_event_coordinator_id', 'in', rec.ike_event_coordinator_ids.ids)
                ])
            else:
                rec.event_assign_ids = False

    def action_assignment_event(self):
        if not self.ike_event_coordinator_id:
            return

        self.event_not_assign_ids.write({
            'ike_event_coordinator_id': self.ike_event_coordinator_id.id
        })
