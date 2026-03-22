# -*- coding: utf-8 -*-

from odoo import fields, models
from odoo.addons.mail.tools.discuss import Store


class MailMessage(models.Model):
    _inherit = 'mail.message'

    o2m_tracking_command_ids = fields.One2many('mail.tracking.command', 'mail_message_id', 'One2many Tracking Commands')

    # === OVERWRITE === #
    def _to_store(self, store: Store, /, *, fields=None, **kwargs):
        """ Extends Store functionality to add o2m tracking messages. """
        super()._to_store(store, fields=fields, **kwargs)
        if kwargs.get('for_current_user', False):
            for key, value in store.data['mail.message'].items():
                message = self.filtered(lambda x: x.id == value['id'])
                if message:
                    value[
                        'o2mTrackings'
                    ] = message.sudo()._o2m_tracking_message_format(
                        value['trackingValues']
                    )
                    value['trackingValues'] = [
                        value_id
                        for value_id in value['trackingValues']
                        if not value_id['o2m_record_id']
                    ]

    def _o2m_tracking_message_format(self, current_tracking_values):
        """ Return structure and formatted data structure to be used by chatter
        to display o2m tracking messages.

        :param current_tracking_values: current tracking values associated to main mail message.

        :return list: for each tracking message in self, their formatted display
          values given as a dict;
        """
        self.ensure_one()

        grouped = {}

        for o2m_command_id in self.o2m_tracking_command_ids:
            field_id = o2m_command_id.o2m_field_id.id
            if field_id not in grouped:
                grouped[field_id] = {
                    "o2m_field_id": field_id,
                    "o2m_field_description": o2m_command_id.o2m_field_id.field_description,
                    "o2mTrackingCommands": []
                }
            o2mTrackingValues = [
                value for value in current_tracking_values
                if value['id'] in o2m_command_id.o2m_tracking_value_ids.ids
            ]
            grouped[field_id]["o2mTrackingCommands"].append(
                {
                    'id': o2m_command_id.id,
                    "o2m_record_name": o2m_command_id.o2m_record_name,
                    "o2m_command": o2m_command_id._fields[
                        'o2m_command'
                    ].convert_to_export(o2m_command_id.o2m_command, o2m_command_id),
                    'o2mTrackingValues': o2mTrackingValues,
                }
            )

        return list(grouped.values())


class MailTrackingValue(models.Model):
    _inherit = 'mail.tracking.value'

    o2m_record_id = fields.Integer('One2many Record')

    o2m_mail_tracking_command_id = fields.Many2one(
        'mail.tracking.command', 'One2many Tracking Command',
        required=False, ondelete='cascade')

    def _tracking_value_format_model(self, model):
        """ Return structure and formatted data structure to be used by chatter
        to display tracking values. Order it according to asked display, aka
        ascending sequence (and field name).

        :return list: for each tracking value in self, their formatted display
          values given as a dict;

        OVERRIDDEN
        """
        if not self:
            return []

        # fetch model-based information
        if model:
            TrackedModel = self.env[model]
            tracked_fields = TrackedModel.fields_get(self.field_id.mapped('name'), attributes={'digits', 'string', 'type'})
            model_sequence_info = dict(TrackedModel._mail_track_order_fields(tracked_fields)) if model else {}
        else:
            tracked_fields, model_sequence_info = {}, {}

        # generate sequence of trackings
        fields_sequence_map = dict(
            {
                tracking.field_info['name']: tracking.field_info.get('sequence', 100)
                for tracking in self.filtered('field_info')
            },
            **model_sequence_info,
        )
        # generate dict of field information, if available
        fields_col_info = (
            tracked_fields.get(tracking.field_id.name) or {
                'string': tracking.field_info['desc'] if tracking.field_info else self.env._('Unknown'),
                'type': tracking.field_info['type'] if tracking.field_info else 'char',
            } for tracking in self
        )

        formatted = [
            {
                'changedField': col_info['string'],
                'id': tracking.id,
                'fieldName': tracking.field_id.name or (tracking.field_info['name'] if tracking.field_info else 'unknown'),
                'o2m_record_id': tracking.o2m_record_id,
                'fieldType': col_info['type'],
                'newValue': {
                    'currencyId': tracking.currency_id.id,
                    'floatPrecision': col_info.get('digits'),
                    'value': tracking._format_display_value(col_info['type'], new=True)[0],
                },
                'oldValue': {
                    'currencyId': tracking.currency_id.id,
                    'floatPrecision': col_info.get('digits'),
                    'value': tracking._format_display_value(col_info['type'], new=False)[0],
                },
            }
            for tracking, col_info in zip(self, fields_col_info)
        ]
        formatted.sort(
            key=lambda info: (fields_sequence_map.get(info['fieldName'], 100), info['fieldName']),
            reverse=False,
        )
        return formatted


class MailTrackingCommand(models.Model):
    _name = 'mail.tracking.command'
    _description = 'One2many Tracking Command'
    _rec_name = 'o2m_field_id'

    mail_message_id = fields.Many2one('mail.message', required=True, index=1, ondelete='cascade')

    o2m_field_id = fields.Many2one(
        'ir.model.fields', 'One2many Field',
        required=False, readonly=False,
        index=True, ondelete='set null')

    o2m_record_id = fields.Integer(string='One2many Record')
    o2m_record_name = fields.Char(string='One2many Record Name')

    o2m_command = fields.Selection([
        ('0', 'Created'),
        ('1', 'Updated'),
        ('2', 'Deleted'),
    ], string='One2many Command')

    o2m_tracking_value_ids = fields.One2many(
        'mail.tracking.value', 'o2m_mail_tracking_command_id', string='One2many Tracking Values')
