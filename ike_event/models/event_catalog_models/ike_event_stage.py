# -*- coding: utf-8 -*-

from odoo import models, fields, api, Command, _

from ..other_models.ike_event_batcher import event_batcher


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
    _order = 'event_id, stage_sequence, sequence'

    _sql_constraints = [
        (
            'unique_event_stage_sequence',
            'unique(event_id, stage_id, sequence)',
            'Someone else has already registered the same comment. Please reopen the window to verify it.'
        ),
    ]

    event_id = fields.Many2one('ike.event', required=True, ondelete='cascade', readonly=True)
    stage_id = fields.Many2one('ike.event.stage', required=True, readonly=True)
    stage_sequence = fields.Integer(related='stage_id.sequence', readonly=True)
    sequence = fields.Integer(required=True, default=1)

    previous_date = fields.Datetime(required=True, readonly=True)
    duration_minutes = fields.Integer('Duration (minutes)', compute='_compute_duration', store=True)
    duration_text = fields.Char('Duration', compute='_compute_duration', store=True)
    elapsed_time_minutes = fields.Integer('Elapsed Time (minutes)', compute='_compute_elapsed_time')

    comment = fields.Text(required=True)

    stage_comment_ids = fields.One2many('ike.event.stage.comment', 'event_id', string='Comments', compute='_compute_stage_comment_ids')

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
                rec.duration_text = (
                    f'{sum(previous.mapped('duration_minutes'))}-{sum(previous.mapped('duration_minutes')) + rec.duration_minutes}'
                )
            else:
                rec.duration_text = f'0-{rec.duration_minutes}'

    @api.depends('create_date')
    def _compute_elapsed_time(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.elapsed_time_minutes = (now - rec.create_date).total_seconds() // 60

    @api.depends('event_id')
    def _compute_stage_comment_ids(self):
        for rec in self:
            rec.stage_comment_ids = self.search([
                ('event_id', '=', rec.event_id.id),
            ])

    def action_dummy_save(self):
        self.ensure_one()

        event_batcher.add_event_notification(
            self.env.cr.dbname,
            'IKE_CHANNEL_LIST',
            'IKE_CHANNEL_LIST_LISTEN', {
                'id': self.event_id.id,
                'stage_ref': self.event_id.stage_ref,
                'ike_uuid': self.env.context.get('ike_uuid'),
            }, batch_timeout=10)

    @api.model_create_multi
    def create(self, vals_list):
        print()
        for vals in vals_list:
            event_id = self.env.context.get('default_event_id', False)
            stage_id = self.env.context.get('default_stage_id', False)
            if event_id and stage_id:
                last_id = self.search([
                    ('event_id', '=', event_id),
                    ('stage_id', '=', stage_id),
                ], order='sequence desc', limit=1)
                sequence = 1
                if last_id:
                    sequence = last_id[0].sequence
                vals['sequence'] = sequence + 1
        return super().create(vals_list)
