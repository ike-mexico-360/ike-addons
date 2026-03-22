# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import models
from odoo.exceptions import MissingError
from odoo.tools import (clean_context, ormcache)


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    # === OVERWRITE === #
    def _valid_field_parameter(self, field, name):
        """allow sub_tracking on models"""
        return name == 'sub_tracking' or super()._valid_field_parameter(field, name)

    def write(self, vals):
        if self._context.get('tracking_disable'):
            return super().write(vals)

        if (
            not self._context.get('mail_notrack')
            and self._context.get('mail_sub_track')
            and self._fields.get(self._parent_name, False)
        ):
            self._o2m_sub_track_prepare(self._fields)

        # Perform write
        result = super().write(vals)

        return result

    # === SUB TRACKING === #
    @ormcache('self.env.uid', 'self.env.su')
    def _o2m_sub_track_get_fields(self):
        """ Return the set of sub-tracked fields names for the current model. """
        model_fields = {
            name
            for name, field in self._fields.items()
            if getattr(field, 'sub_tracking', None)
        }

        return model_fields and set(self.fields_get(model_fields, attributes=()))

    def _o2m_sub_track_prepare(self, fields_iter):
        """ Prepare the sub-tracking of ``fields_iter`` for ``self``.

        :param iter fields_iter: iterable of fields names to potentially track
        """
        fnames = self._o2m_sub_track_get_fields().intersection(fields_iter)
        if not fnames:
            return
        self.env.cr.precommit.add(self._o2m_sub_track_finalize)
        initial_values = self.env.cr.precommit.data.setdefault(f'mail.tracking.{self._name}', {})
        for record in self:
            if not record.id:
                continue
            values = initial_values.setdefault(record.id, {})
            if values is not None:
                for fname in fnames:
                    values.setdefault(fname, record[fname])
                    # FIXE DELETED ONES
                    if record._fields[fname].type in ['one2many', 'many2many']:
                        o2m_data = {
                            r.id: {
                                'id': r.id,
                                'display_name': r.display_name,
                            }
                            for r in record[fname]
                        }
                        values.setdefault('o2m_' + fname, o2m_data)
        # print("TEST", values)

    def _o2m_sub_track_finalize(self):
        """ Generate the sub-tracking messages for the records that have been
        prepared with ``_tracking_prepare``.
        """
        initial_values = self.env.cr.precommit.data.pop(f'mail.tracking.{self._name}', {})
        ids = [id_ for id_, vals in initial_values.items() if vals]
        if not ids:
            return
        records = self.browse(ids).sudo()
        fnames = self._o2m_sub_track_get_fields()
        context = clean_context(self._context)
        records.with_context(context)._o2m_message_sub_track(fnames, initial_values)
        self.env.flush_all()

    def _o2m_message_sub_track(self, fields_iter, initial_values_dict):
        """ Sub-Track updated values. Comparing the initial and current values of
        the fields given in tracked_fields, it generates a message containing
        the updated values. This message can be linked to a mail.message.subtype
        given by the ``_track_subtype`` method.

        :param iter fields_iter: iterable of field names to track
        :param dict initial_values_dict: mapping {record_id: initial_values}
          where initial_values is a dict {field_name: value, ... }
        :return: mapping {record_id: (changed_field_names, tracking_value_ids)}
            containing existing records only
        """
        if not fields_iter:
            return {}

        tracked_fields = self.fields_get(fields_iter, attributes=('string', 'type', 'selection', 'currency_field'))
        tracking = dict()
        for record in self:
            try:
                tracking[record.id] = record._o2m_mail_sub_track(tracked_fields, initial_values_dict[record.id])
            except MissingError:
                continue

        for record in self:
            changes, tracking_value_ids = tracking.get(record.id, (None, None))
            if not changes:
                continue

            author_id = None
            # record._fields[self._parent_name].get_description(self.env)["string"]
            if tracking_value_ids:
                record[record._parent_name]._message_log(
                    body=Markup("<b>%s:</b> %s")
                    % (
                        self.env['ir.model']._get(record._name).display_name,
                        record.display_name,
                    ),
                    author_id=author_id,
                    tracking_value_ids=tracking_value_ids,
                )

        return tracking

    def _o2m_mail_sub_track(self, tracked_fields, initial_values):
        """ For a given record, fields to check (tuple column name, column info)
        and initial values, return a valid command to create tracking values.

        :param dict tracked_fields: fields_get of updated fields on which
          tracking is checked and performed;
        :param dict initial_values: dict of initial values for each updated
          fields;

        :return: a tuple (changes, tracking_value_ids) where
          changes: set of updated column names; contains onchange tracked fields
          that changed;
          tracking_value_ids: a list of ORM (0, 0, values) commands to create
          ``mail.tracking.value`` records;

        Override this method on a specific model to implement model-specific
        behavior. Also consider inheriting from ``mail.thread``. """
        self.ensure_one()
        updated = set()
        tracking_value_ids = []

        fields_track_info = self._mail_track_order_fields(tracked_fields)
        for col_name, _sequence in fields_track_info:
            if col_name not in initial_values:
                continue
            initial_value, new_value = initial_values[col_name], self[col_name]
            col_info = tracked_fields[col_name]
            # FIXED
            if col_info['type'] in ['one2many', 'many2many']:
                initial_value = ', '.join([value['display_name'] for key, value in initial_values['o2m_' + col_name].items()])
                new_value = ', '.join(new_value.mapped('display_name'))
                col_info['type'] = 'char'
            if new_value == initial_value or (not new_value and not initial_value):  # because browse null != False
                continue

            updated.add(col_name)
            tracking_value_ids.append(
                [0, 0, self.env['mail.tracking.value']._create_tracking_values(
                    initial_value, new_value,
                    col_name, col_info,
                    self
                )])

        return updated, tracking_value_ids
