# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from markupsafe import Markup


class IkeEventSupplierAssignment(models.Model):
    _name = 'ike.event.supplier.assignment.type'
    _inherit = ['mail.thread']
    _description = 'Event Supplier Assignment Type'
    _order = 'sequence, name'

    name = fields.Char(string='Assignment Type', translate=True, required=True, tracking=True)
    sequence = fields.Integer(
        string='Assignment Order',
        default=lambda self: self._get_next_sequence(),
        tracking=True,
    )
    wait_time = fields.Integer(help='Maximum waiting time to accept the service, in seconds.', default=40, tracking=True)
    geofence_radius_meters = fields.Integer(tracking=True)
    geofence_radius = fields.Float(compute="_compute_geofence_radius", store=True)
    arrival_duration = fields.Integer(help='Average time to accept the service, in minutes.', tracking=True)
    max_suppliers = fields.Integer(default=6, tracking=True)
    by_priority = fields.Boolean(tracking=True)
    total_assignment_time = fields.Float(
        compute="_compute_total_assignment_time",
        tracking=True,
        digits=(10, 1),
        store=True,
    )
    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

    def _get_next_sequence(self):
        highest_sequence = self.env['ike.event.supplier.assignment.type'].search_read(
            [('sequence', '!=', False)], ['sequence'], order='sequence DESC', limit=1
        )
        sequence = 1
        if len(highest_sequence):
            sequence = highest_sequence[0]['sequence'] + 1
        return sequence

    @api.depends('geofence_radius_meters')
    def _compute_geofence_radius(self):
        for rec in self:
            rec.geofence_radius = rec.geofence_radius_meters / 1000.0

    @api.depends('wait_time', 'by_priority', 'max_suppliers')
    def _compute_total_assignment_time(self):
        for rec in self:
            rec.total_assignment_time = (
                rec.wait_time
                if rec.by_priority
                else rec.wait_time * rec.max_suppliers
            ) / 60
