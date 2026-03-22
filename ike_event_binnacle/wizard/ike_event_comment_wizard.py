from odoo import models, fields, api, _
from datetime import datetime


class IkeEventCommentWizard(models.TransientModel):
    _name = 'ike.event.comment.wizard'
    _description = 'Event Comment Wizard'

    event_id = fields.Many2one(
        'ike.event',
        required=True
    )
    body = fields.Html(
        string='Comment',
        required=True
    )
    event_binnacle_id = fields.Many2one(
        'ike.event.binnacle',
        compute="_compute_event_binnacle"
    )

    # === COMPUTE === #
    @api.depends('event_id')
    def _compute_event_binnacle(self):
        for rec in self:
            rec.event_binnacle_id = False
            message_id = rec._get_last_message_event()

            if not message_id or not message_id.event_binnacle_id:
                continue

            event_binnacle_id = self.env['ike.event.binnacle'].sudo().search([
                ('disabled', '=', False),
                ('event_stage_id', '=', message_id.event_binnacle_id.event_stage_id.id),
                ('step_number', '=', message_id.event_binnacle_id.step_number),
                ('binnacle_category_id.name', '=', 'Resumen'),
            ], limit=1)

            rec.event_binnacle_id = event_binnacle_id

    # === METHODS === #
    def _get_last_message_event(self):
        message_id = self.env['mail.message'].sudo().search([
            ('event_binnacle_id', '!=', False),
            ('model', '=', "ike.event"),
            ('res_id', '=', self.event_id.id),
        ], order='create_date desc', limit=1)

        return message_id

    # === ACTIONS === #
    def action_save_confirm(self):
        self.ensure_one()

        self.env['mail.message'].create({
            'model': 'ike.event',
            'res_id': self.event_id.id,
            'body': self.body,
            'message_type': 'comment',
            'subtype_id': self.env.ref('mail.mt_comment').id,
            'author_id': self.env.user.partner_id.id,
            'is_internal': False,
            'event_binnacle_id': self.event_binnacle_id.id,
        })

        return {'type': 'ir.actions.act_window_close'}
