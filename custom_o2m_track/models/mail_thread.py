# -*- coding: utf-8 -*-

import logging

from markupsafe import escape

from odoo import models, _
from odoo.exceptions import MissingError
from odoo.tools.mail import (generate_tracking_message_id)

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _get_message_create_valid_field_names(self):
        res = super()._get_message_create_valid_field_names()
        res.add('o2m_tracking_command_ids')
        return res

    def _track_prepare(self, fields_iter):
        """ Prepare the tracking of ``fields_iter`` for ``self``.

        :param iter fields_iter: iterable of fields names to potentially track

        Overridden for One2many detailed tracking
        """
        fnames = self._track_get_fields().intersection(fields_iter)
        if not fnames:
            return
        self.env.cr.precommit.add(self._track_finalize)
        initial_values = self.env.cr.precommit.data.setdefault(f'mail.tracking.{self._name}', {})
        for record in self:
            if not record.id:
                continue
            values = initial_values.setdefault(record.id, {})
            if values is not None:
                for fname in fnames:
                    values.setdefault(fname, record[fname])
                    # O2M ADDED
                    if record._fields[fname].type == 'one2many':
                        sub_fields_iter = record[fname]._o2m_sub_track_get_fields()
                        o2m_values = {
                            r.id: {
                                'id': r.id,
                                'display_name': r.display_name,
                                **{field: r[field] for field in sub_fields_iter}
                            }
                            for r in record[fname]
                        }
                        values.setdefault('o2m_' + fname, o2m_values)

    def _message_track(self, fields_iter, initial_values_dict):
        """ Track updated values. Comparing the initial and current values of
        the fields given in tracked_fields, it generates a message containing
        the updated values. This message can be linked to a mail.message.subtype
        given by the ``_track_subtype`` method.

        :param iter fields_iter: iterable of field names to track
        :param dict initial_values_dict: mapping {record_id: initial_values}
          where initial_values is a dict {field_name: value, ... }
        :return: mapping {record_id: (changed_field_names, tracking_value_ids)}
            containing existing records only

        Overridden for One2many detailed tracking
        """
        if not fields_iter:
            return {}

        tracked_fields = self.fields_get(fields_iter, attributes=('string', 'type', 'selection', 'currency_field'))
        o2m_tracked_fields = {k: v for k, v in tracked_fields.items() if v.get('type') == 'one2many'}
        tracked_fields = {k: v for k, v in tracked_fields.items() if v.get('type') != 'one2many'}
        tracking = dict()
        for record in self:
            try:
                tracking[record.id] = record._mail_track(tracked_fields, initial_values_dict[record.id])
            except MissingError:
                continue

        # O2M ADDED
        o2m_tracking = dict()
        o2m_tracking_value_ids = []
        for record in self:
            try:
                o2m_tracking[record.id] = []
                for o2m_field_name in o2m_tracked_fields.keys():
                    old_data = initial_values_dict[record.id][o2m_field_name]
                    current_data = getattr(record, o2m_field_name)
                    o2m_field = self.env['ir.model.fields']._get(record._name, o2m_field_name)

                    current_ids = set(current_data.ids)
                    old_ids = set(old_data.ids)

                    deleted_ids = old_ids - current_ids
                    for line_id in deleted_ids:
                        old_line = initial_values_dict[record.id]['o2m_' + o2m_field_name][line_id]
                        o2m_tracking[record.id].append([0, 0, {
                            'o2m_command': '2',
                            'o2m_field_id': o2m_field.id,
                            'o2m_record_id': line_id,
                            'o2m_record_name': old_line['display_name'],
                        }])

                    added_ids = current_ids - old_ids
                    for line_id in added_ids:
                        current_line_id = current_data.filtered(lambda x: x.id == line_id)
                        o2m_tracking[record.id].append([0, 0, {
                            'o2m_command': '0',
                            'o2m_field_id': o2m_field.id,
                            'o2m_record_id': line_id,
                            'o2m_record_name': current_line_id.display_name,
                        }])

                    sub_tracking = dict()
                    sub_fields_iter = current_data._o2m_sub_track_get_fields()
                    sub_tracked_fields = current_data.fields_get(
                        sub_fields_iter,
                        attributes=('string', 'type', 'selection', 'currency_field'))
                    updated_ids = old_ids & current_ids
                    for line_id in updated_ids:
                        old_line = initial_values_dict[record.id]['o2m_' + o2m_field_name][line_id]
                        current_line_id = current_data.filtered(lambda x: x.id == line_id)
                        if not sub_fields_iter:
                            continue
                        sub_tracking[record.id] = current_line_id._mail_track(sub_tracked_fields, old_line)
                        changes, _tracking_value_ids = sub_tracking.get(record.id, (None, None))

                        o2m_tracking_values = []
                        for value_id in _tracking_value_ids:
                            value_id[2]['o2m_record_id'] = line_id
                            o2m_tracking_values.append(value_id)
                        if len(o2m_tracking_values):
                            o2m_tracking[record.id].append([0, 0, {
                                'o2m_command': '1',
                                'o2m_field_id': o2m_field.id,
                                'o2m_record_id': line_id,
                                'o2m_record_name': current_line_id.display_name,
                            }])
                            o2m_tracking_value_ids.extend(o2m_tracking_values)

            except MissingError:
                continue

        # find content to log as body
        bodies = self.env.cr.precommit.data.pop(f'mail.tracking.message.{self._name}', {})
        authors = self.env.cr.precommit.data.pop(f'mail.tracking.author.{self._name}', {})
        for record in self:
            changes, tracking_value_ids = tracking.get(record.id, (None, None))

            o2m_tracking_command_ids = o2m_tracking.get(record.id, (None, None))

            if not changes and not o2m_tracking_command_ids:
                continue

            # find subtypes and post messages or log if no subtype found
            subtype = record._track_subtype(
                dict((col_name, initial_values_dict[record.id][col_name])
                     for col_name in changes)
            )
            author_id = authors[record.id].id if record.id in authors else None
            # _set_log_message takes priority over _track_get_default_log_message even if it's an empty string
            body = bodies[record.id] if record.id in bodies else record._track_get_default_log_message(changes)
            if subtype:
                if not subtype.exists():
                    _logger.debug('subtype "%s" not found' % subtype.name)
                    continue
                record.message_post(
                    body=body,
                    author_id=author_id,
                    subtype_id=subtype.id,
                    tracking_value_ids=tracking_value_ids
                )
            elif tracking_value_ids or o2m_tracking_command_ids or o2m_tracking_value_ids:
                mail_message_id = record._o2m_message_log(
                    body=body,
                    author_id=author_id,
                    tracking_value_ids=tracking_value_ids + o2m_tracking_value_ids,
                    o2m_tracking_command_ids=o2m_tracking_command_ids,
                )

                for value_id in mail_message_id.tracking_value_ids.filtered(lambda x: x.o2m_record_id):
                    command_id = mail_message_id.o2m_tracking_command_ids.filtered(
                        lambda x: x.o2m_record_id == value_id.o2m_record_id)
                    value_id.o2m_mail_tracking_command_id = command_id.id

        return tracking

    def _o2m_message_log(
        self,
        *,
        body='',
        subject=False,
        author_id=None,
        email_from=None,
        message_type='notification',
        partner_ids=False,
        attachment_ids=False,
        tracking_value_ids=False,
        o2m_tracking_command_ids=False,
    ):
        """ Shortcut allowing to post note on a document. See ``_message_log_batch``
        for more details. """
        self.ensure_one()

        return self._o2m_message_log_batch(
            {self.id: body}, subject=subject,
            author_id=author_id, email_from=email_from,
            message_type=message_type,
            partner_ids=partner_ids,
            attachment_ids=attachment_ids,
            tracking_value_ids=tracking_value_ids,
            o2m_tracking_command_ids=o2m_tracking_command_ids,
        )

    def _o2m_message_log_batch(
        self,
        bodies,
        subject=False,
        author_id=None,
        email_from=None,
        message_type='notification',
        partner_ids=False,
        attachment_ids=False,
        tracking_value_ids=False,
        o2m_tracking_command_ids=False,
    ):
        """ Copy of original _message_log_batch """
        # protect against side-effect prone usage
        if len(self) > 1 and (attachment_ids or tracking_value_ids):
            raise ValueError(_('Batch log cannot support attachments or tracking values on more than 1 document'))

        author_id, email_from = self._message_compute_author(author_id, email_from, raise_on_email=False)

        base_message_values = {
            # author
            'author_id': author_id,
            'email_from': email_from,
            # document
            'model': self._name,
            'record_alias_domain_id': False,
            'record_company_id': False,
            'record_name': False,
            # content
            'attachment_ids': attachment_ids,
            'message_type': message_type,
            'is_internal': True,
            'subject': subject,
            'subtype_id': self.env['ir.model.data']._xmlid_to_res_id('mail.mt_note'),
            'tracking_value_ids': tracking_value_ids,
            # recipients
            'email_add_signature': False,  # False as no notification -> no need to compute signature
            'message_id': generate_tracking_message_id('message-notify'),  # why? this is all but a notify
            'partner_ids': partner_ids,
            'reply_to': self.env['mail.thread']._notify_get_reply_to(default=email_from)[False],
            'o2m_tracking_command_ids': o2m_tracking_command_ids,
        }

        values_list = [dict(base_message_values,
                            res_id=record.id,
                            body=escape(bodies.get(record.id, '')))
                       for record in self]
        return self.sudo()._message_create(values_list)
