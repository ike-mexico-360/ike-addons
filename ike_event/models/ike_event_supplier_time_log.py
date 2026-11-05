# -*- coding: utf-8 -*-
import logging

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)

# stage_key: (first_cols, current_cols); cada uno = (date, user, comment) en ike_event_supplier
LEGACY_STAGE_COLUMNS = {
    'first_state': (
        ('first_state_date', 'first_state_user_id', 'first_comment'),
        ('first_state_date', 'first_state_user_id', 'first_comment'),
    ),
    'assigned': (
        ('first_assignation_date', 'first_assignation_user_id', 'first_assignation_comment'),
        ('assignation_date', 'assignation_user_id', 'assignation_comment'),
    ),
    'on_route': (
        ('first_on_route_to_user_start_date', 'first_on_route_to_start_user_id', 'first_on_route_to_start_comment'),
        ('on_route_to_user_start_date', 'on_route_to_start_user_id', 'on_route_to_start_comment'),
    ),
    'arrived': (
        ('first_on_route_to_user_end_date', 'first_on_route_to_end_user_id', 'first_on_route_to_end_comment'),
        ('on_route_to_user_end_date', 'on_route_to_end_user_id', 'on_route_to_end_comment'),
    ),
    'contacted': (
        ('first_contacted_date', 'first_contacted_user_id', 'first_contacted_comment'),
        ('contacted_date', 'contacted_user_id', 'contacted_comment'),
    ),
    'on_route_destination': (
        ('first_on_route_to_destination_start_date', 'first_on_route_to_destination_start_user_id',
         'first_on_route_to_destination_start_comment'),
        ('on_route_to_destination_start_date', 'on_route_to_destination_start_user_id',
         'on_route_to_destination_start_comment'),
    ),
    'arrived_destination': (
        ('first_on_route_to_destination_end_date', 'first_on_route_to_destination_end_user_id',
         'first_on_route_to_destination_end_comment'),
        ('on_route_to_destination_end_date', 'on_route_to_destination_end_user_id',
         'on_route_to_destination_end_comment'),
    ),
    'finalized': (
        ('first_finalized_date', 'first_finalized_user_id', 'first_finalized_comment'),
        ('finalized_date', 'finalized_user_id', 'finalized_comment'),
    ),
}


class IkeEventSupplierTimeLog(models.Model):
    _name = 'ike.event.supplier.time.log'
    _description = 'Event Supplier Time Log'
    _order = 'date desc, id desc'

    event_supplier_id = fields.Many2one(
        'ike.event.supplier',
        string='Supplier Event',
        required=True,
        ondelete='cascade',
        index=True
    )

    stage_key = fields.Selection([
        ('first_state', 'First State'),
        ('assigned', 'Assigned'),
        ('on_route', 'On Route'),
        ('arrived', 'Arrived'),
        ('contacted', 'Contacted'),
        ('on_route_destination', 'Route to Destination'),
        ('arrived_destination', 'Arrived Destination'),
        ('finalized', 'Finalized'),
    ], string='Stage Key', required=True, index=True)

    stage_id = fields.Many2one(
        'ike.service.stage',
        string='Stage'
    )

    is_first = fields.Boolean(
        string='Is First Record',
        default=False,
        help='Technical flag to differentiate initial timestamp from update timestamps'
    )

    date = fields.Datetime(
        string='Datetime',
        required=True,
        default=fields.Datetime.now
    )

    user_id = fields.Many2one(
        'res.users',
        string='User',
        default=lambda self: self.env.user,
        readonly=True
    )

    comment = fields.Text(string='Comment')

    # ------------------------------------------------------------------ #
    # DATA MIGRATION (run manually from the inactive cron)
    # ------------------------------------------------------------------ #
    @api.model
    def _legacy_column_exists(self, column):
        self.env.cr.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            ('ike_event_supplier', column),
        )
        return bool(self.env.cr.fetchone())

    @api.model
    def _migrate_legacy_columns(self, stage_key, is_first, columns, id_from, id_to, existing_cols):
        """
        Inserts logs from a triad of legacy columns, for suppliers with IDs in [id_from, id_to].
        Idempotent: skips log creation if a record already exists for (supplier, stage_key, is_first).
        """
        date_col, user_col, comment_col = columns
        if date_col not in existing_cols:
            return 0

        user_expr = f's.{user_col}' if user_col in existing_cols else 'NULL'
        comment_expr = f's.{comment_col}' if comment_col in existing_cols else 'NULL'

        # Column names come from LEGACY_STAGE_COLUMNS (constant), not external input
        self.env.cr.execute(f"""
            INSERT INTO ike_event_supplier_time_log
                (event_supplier_id, stage_key, is_first, date, user_id, comment,
                 create_uid, create_date, write_uid, write_date)
            SELECT s.id, %(stage_key)s, %(is_first)s, s.{date_col}, {user_expr}, {comment_expr},
                   %(uid)s, (now() at time zone 'UTC'), %(uid)s, (now() at time zone 'UTC')
              FROM ike_event_supplier s
             WHERE s.id BETWEEN %(id_from)s AND %(id_to)s
               AND s.{date_col} IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1 FROM ike_event_supplier_time_log l
                    WHERE l.event_supplier_id = s.id
                      AND l.stage_key = %(stage_key)s
                      AND l.is_first = %(is_first)s
               )
        """, {
            'stage_key': stage_key,
            'is_first': is_first,
            'uid': self.env.uid,
            'id_from': id_from,
            'id_to': id_to,
        })
        return self.env.cr.rowcount

    @api.model
    def _cron_migrate_legacy_stage_fields(self, batch_size=5000):
        """
        Migrates stage fields from ike.event.supplier (first_* / *_date / *_user_id / *_comment
        and first_state_*) to ike.event.supplier.time.log.

        - Processes in ID ranges and commits per batch: if the cron times out,
        already migrated records remain saved and re-running it is sufficient (it is idempotent).
        - Initial record (is_first=True): uses first_*; if empty, uses the current value.
        - Current record (is_first=False): uses the current value; if empty, uses first_*.
        (matching the behavior of _register_stage_time)
        """
        cr = self.env.cr

        # Old columns that actually exist in the DB (queried only once)
        all_cols = {col for cols in LEGACY_STAGE_COLUMNS.values() for terna in cols for col in terna}
        existing_cols = {col for col in all_cols if self._legacy_column_exists(col)}
        missing = all_cols - existing_cols
        if missing:
            _logger.info('[time.log migration] Columnas inexistentes, se omiten: %s', sorted(missing))

        cr.execute("SELECT MIN(id), MAX(id) FROM ike_event_supplier")
        min_id, max_id = cr.fetchone()
        if not min_id:
            _logger.info('[time.log migration] No hay suppliers que migrar')
            return

        _logger.info('[time.log migration] Inicio: ids %s-%s, lotes de %s', min_id, max_id, batch_size)
        totals = {key: [0, 0] for key in LEGACY_STAGE_COLUMNS}

        for id_from in range(min_id, max_id + 1, batch_size):
            id_to = min(id_from + batch_size - 1, max_id)

            for stage_key, (first_cols, current_cols) in LEGACY_STAGE_COLUMNS.items():
                # Initial: first_* and, if none exists, the current one
                totals[stage_key][0] += self._migrate_legacy_columns(
                    stage_key, True, first_cols, id_from, id_to, existing_cols)
                totals[stage_key][0] += self._migrate_legacy_columns(
                    stage_key, True, current_cols, id_from, id_to, existing_cols)
                # Current: the current one and, if none exists, first_*
                totals[stage_key][1] += self._migrate_legacy_columns(
                    stage_key, False, current_cols, id_from, id_to, existing_cols)
                totals[stage_key][1] += self._migrate_legacy_columns(
                    stage_key, False, first_cols, id_from, id_to, existing_cols)

            # Save the batch progress (the direct SQL INSERTs do not go through the ORM cache)
            cr.commit()
            _logger.info('[time.log migration] Lote %s-%s migrado', id_from, id_to)

        for stage_key, (first_count, current_count) in totals.items():
            _logger.info(
                '[time.log migration] %s: %s iniciales, %s actuales',
                stage_key, first_count, current_count,
            )
        _logger.info('[time.log migration] Fin')
