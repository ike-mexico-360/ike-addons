from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CustomHelpdeskStageTimeGroup(models.Model):
    _name = 'custom.helpdesk.stage.time.group'
    _description = 'Accumulated time by stages'

    name = fields.Char(required=True)
    stage_ids = fields.Many2many(
        'helpdesk.stages',
        'custom_helpdesk_stage_time_group_helpdesk_stages_rel',
        'time_group_id',
        'stage_id',
        string='Stages',
        required=True,
    )
    max_wait_time = fields.Float(string='Maximum wait time', required=True)
    max_wait_time_unit = fields.Selection(
        selection=[
            ('minutes', 'Minutes'),
            ('hours', 'Hours'),
            ('days', 'Days'),
        ],
        string='Time unit',
        required=True,
        default='minutes',
    )

    @api.constrains('max_wait_time')
    def _check_max_wait_time(self):
        if any(record.max_wait_time <= 0 for record in self):
            raise ValidationError(_('Maximum wait time must be greater than zero.'))

    @api.constrains('stage_ids')
    def _check_unique_stages(self):
        for record in self:
            duplicate = self.search([
                ('id', '!=', record.id),
                ('stage_ids', 'in', record.stage_ids.ids),
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'A stage can belong to only one accumulated time configuration.'
                ))

    def _max_wait_time_seconds(self):
        self.ensure_one()
        multiplier = {
            'minutes': 60,
            'hours': 3600,
            'days': 86400,
        }[self.max_wait_time_unit]
        return round(self.max_wait_time * multiplier)
