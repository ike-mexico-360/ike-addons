# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from markupsafe import Markup


class IkeEventBinnacle(models.Model):
    _name = 'ike.event.binnacle'
    _description = 'Event Binnacle'
    _inherit = ['mail.thread']
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=False, default="/")
    event_stage_id = fields.Many2one('ike.event.stage', tracking=True)
    binnacle_category_id = fields.Many2one('ike.event.binnacle.category', tracking=True)
    step_number = fields.Integer(tracking=True)
    description = fields.Char(tracking=True)
    binnacle_template_id = fields.Many2one('mail.template', tracking=True)
    text_html = fields.Html(related="binnacle_template_id.body_html", translate=True)
    sequence = fields.Integer(default=lambda self: self._get_next_sequence())

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

    def _get_next_sequence(self):
        highest_sequence = self.env['ike.event.binnacle'].search_read(
            [('sequence', '!=', False)], ['sequence'], order='sequence DESC', limit=1
        )
        sequence = 1
        if len(highest_sequence):
            sequence = highest_sequence[0]['sequence'] + 1
        return sequence

    @api.depends('event_stage_id', 'step_number', 'binnacle_category_id')
    @api.depends_context('lang')
    def _compute_name(self):
        for record in self:
            lang = self.env.context.get('lang') or 'en_US'

            stage = record.event_stage_id.with_context(lang=lang)
            category = record.binnacle_category_id.with_context(lang=lang)

            stage_name = stage.name or ''
            category_name = category.name or ''
            step = record.step_number or 0

            step_label = _("paso")

            record.name = f"{stage_name} / {step_label} {step} / {category_name}"

    # === ACTIONS === #
    def action_disable(self, reason=None):
        for rec in self:
            if reason:
                body = Markup("""
                    <ul class="mb-0 ps-4">
                        <li>
                            <b>{}: </b><span class="">{}</span>
                        </li>
                    </ul>
                """).format(
                    _('Disabled'),
                    reason,
                )
                rec.message_post(
                    body=body,
                    message_type='notification',
                    body_is_html=True)
        return super().action_disable(reason)
