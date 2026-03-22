# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _


class IkeEventFlow(models.Model):
    _name = 'ike.event.flow'
    _description = 'Event Flow'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    note = fields.Html()
    sequence = fields.Integer(default=20)
    stage_id = fields.Many2one('ike.event.stage', required=True)
    step_number = fields.Integer(default=1, aggregator='max', required=True)
    condition_domain = fields.Char(string='Domain')
    active = fields.Boolean(default=True)

    detail_ids = fields.One2many('ike.event.flow.detail', 'event_flow_id')

    section_ids = fields.One2many(
        'ike.event.flow.detail', 'event_flow_id',
        domain=[('detail_type', '=', 'section')])

    action_ids = fields.One2many(
        'ike.event.flow.detail', 'event_flow_id',
        domain=[('detail_type', '=', 'action')])

    summary_top_ids = fields.One2many(
        'ike.event.flow.detail', 'event_flow_id',
        domain=[('detail_type', '=', 'summary_top')])
    summary_bottom_ids = fields.One2many(
        'ike.event.flow.detail', 'event_flow_id',
        domain=[('detail_type', '=', 'summary_bottom')])


class IkeEventFlowSection(models.Model):
    _name = 'ike.event.flow.detail'
    _description = 'Event Flow Detail'
    _order = 'sequence'

    event_flow_id = fields.Many2one('ike.event.flow', ondelete='cascade', required=True)
    name = fields.Char(required=True)
    sequence = fields.Integer(default=10, required=True)
    detail_type = fields.Selection([
        ('section', 'Section'),
        ('action', 'Action'),
        ('summary_top', 'Summary Top'),
        ('summary_bottom', 'Summary Bottom'),
    ], required=True)
    service_specific = fields.Char()
