# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _


class IkeEventStage(models.Model):
    _name = 'ike.event.stage'
    _description = 'Event Stage'
    _order = 'sequence, id'

    name = fields.Char(translate=True)
    ref = fields.Char()
    sequence = fields.Integer(default=1)
    color = fields.Char()
    fold = fields.Boolean(default=False)
    flow_path = fields.Char()
    hide_timer = fields.Boolean(default=False)
    last_stage = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    # Tracking/Max Times
    apply_max_wait_time = fields.Boolean(default=False)
    max_wait_time_minutes = fields.Integer('Max Wait Time (minutes)', default=0)

    apply_tracking_time = fields.Boolean(default=False)
    tracking_time_minutes = fields.Integer('Tracking Time (minutes)', default=0)


class IkeEventStageComment(models.Model):
    _name = 'ike.event.stage.comment'
    _description = 'Event Stage Comment'
    _order = 'event_id, stage_id, sequence'

    event_id = fields.Many2one('ike.event', required=True, ondelete='cascade')
    stage_id = fields.Many2one('ike.event.stage', required=True)
    sequence = fields.Integer(required=True, default=1)

    previous_date = fields.Datetime(required=True)
    duration_minutes = fields.Integer('Duration (minutes)', compute='_compute_duration', store=True)
    duration_text = fields.Char('Duration', compute='_compute_duration', store=True)

    comments = fields.Text(required=True)

    @api.depends('create_date', 'previous_date')
    def _compute_duration(self):
        for rec in self:
            if not rec.event_id or not rec.stage_id or not rec.sequence:
                rec.duration_minutes = 0
                rec.duration_text = '0'
            if rec.create_date:
                rec.duration_minutes = int((rec.create_date - rec.previous_date).total_seconds() // 60)
            else:
                rec.duration_minutes = 0
            if rec.sequence > 1:
                previous = self.search([
                    ('event_id', '=', rec.event_id.id),
                    ('stage_id', '=', rec.stage_id.id),
                    ('sequence', '<', rec.sequence),
                ])
                rec.duration_text = f'{sum(previous.mapped('duration_minutes'))}-{rec.duration_minutes}'
            else:
                rec.duration_text = f'0-{rec.duration_minutes}'
