# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools, _
import logging

_logger = logging.getLogger(__name__)


class IkeEventServiceCountDetail(models.Model):
    _name = 'ike.event.service.count.detail'
    _description = 'Event Service Detail Count'
    _rec_name = 'user_membership_id'

    event_service_count_id = fields.Many2one('ike.event.service.count', readonly=True)
    user_membership_plan_id = fields.Many2one('custom.membership.plan', readonly=True)
    user_id = fields.Many2one('custom.nus', readonly=True)
    service_id = fields.Many2one('product.category', readonly=True)
    sub_service_ids = fields.Many2many('product.product',
                                       'event_count_detail_product_rel',
                                       'detail_count_id',
                                       'product_id',
                                       string='Subservices',
                                       readonly=True)
    user_membership_id = fields.Many2one('custom.membership.nus', 'Membership', readonly=True)
    date_start = fields.Date(readonly=True)
    date_end = fields.Date(readonly=True)
    coverage_events = fields.Integer(readonly=True)
    period = fields.Selection([
        ('monthly', 'Monthly'),
        ('biannually', 'Biannually'),
        ('quarterly', 'Quarterly'),
        ('annually', 'Annually'),
    ], string='Period event')
    events_of_period = fields.Integer(readonly=True)
    status = fields.Boolean(readonly=True)
    event_ids = fields.One2many('ike.event.service.summary', 'event_service_detail_count_id', string='Details membership')
    vehicle_weight_category_id = fields.Many2one(
        'custom.vehicle.weight.category',
        'Weight Category',
        domain="[('disabled', '=', False)]")


class IkeEventServiceCount(models.Model):
    _name = 'ike.event.service.count'
    _description = 'Event Service Count Summary'
    _auto = False
    _rec_name = 'user_id'

    user_membership_plan_id = fields.Many2one('custom.membership.plan', readonly=True)
    account_id = fields.Many2one('res.partner', related='user_membership_plan_id.account_id', readonly=True)
    user_id = fields.Many2one('custom.nus', readonly=True)
    service_id = fields.Many2one('product.category', readonly=True)
    sub_service_ids = fields.Many2many(
        'product.product',
        'ike_event_service_count_subservice_rel',
        'count_id',
        'product_id',
        string='Subservices',
        readonly=True
    )
    total_events = fields.Integer(readonly=True)
    detail_ids = fields.Many2many(
        'ike.event.service.count.detail',
        compute='_compute_detail_ids',
        string='Details membership'
    )
    detail_ids_array = fields.Char(readonly=True)
    subservice_array = fields.Char(readonly=True)

    def _compute_detail_ids(self):
        for record in self:
            if record.detail_ids_array:
                ids_str = record.detail_ids_array.strip('{}')
                if ids_str:
                    detail_ids = [int(x) for x in ids_str.split(',')]
                    record.detail_ids = [(6, 0, detail_ids)]
                else:
                    record.detail_ids = [(5, 0, 0)]
            else:
                record.detail_ids = [(5, 0, 0)]

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'ike_event_service_count')

        # La tabla M2M correcta según tu modelo
        m2m_table = 'event_count_detail_product_rel'
        m2m_detail_column = 'detail_count_id'

        _logger.info(f"=== Usando tabla M2M: {m2m_table} ===")

        # Verificar que la tabla existe
        self.env.cr.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            )
        """, (m2m_table,))

        table_exists = self.env.cr.fetchone()[0]
        _logger.info(f"Tabla {m2m_table} existe: {table_exists}")

        if not table_exists:
            _logger.warning(f"Tabla {m2m_table} no existe, creando vista sin subservicios")
            # Crear vista sin subservicios
            self.env.cr.execute("""
                CREATE OR REPLACE VIEW ike_event_service_count AS (
                    WITH all_details AS (
                        SELECT
                            cmn.nus_id as user_id,
                            iesc.user_membership_plan_id,
                            iesc.service_id,
                            iesc.events_of_period,
                            iesc.id as detail_id
                        FROM
                            ike_event_service_count_detail iesc
                            INNER JOIN custom_membership_nus cmn ON iesc.user_membership_id = cmn.id
                    ),
                    grouped_data AS (
                        SELECT
                            user_id,
                            user_membership_plan_id,
                            service_id,
                            SUM(events_of_period) as total_events,
                            array_agg(detail_id ORDER BY detail_id) as detail_ids_array,
                            MIN(detail_id) as min_id
                        FROM
                            all_details
                        GROUP BY
                            user_id,
                            user_membership_plan_id,
                            service_id
                    )
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY user_id, service_id, min_id) as id,
                        user_id,
                        user_membership_plan_id,
                        service_id,
                        total_events,
                        detail_ids_array::text as detail_ids_array,
                        '{}'::text as subservice_array
                    FROM
                        grouped_data
                )
            """)
        else:
            # Crear vista CON subservicios
            _logger.info(f"Creando vista con subservicios usando tabla: {m2m_table}")

            query = f"""
                CREATE OR REPLACE VIEW ike_event_service_count AS (
                    WITH detail_subservices AS (
                        SELECT
                            iesc.id as detail_id,
                            iesc.user_membership_plan_id,
                            iesc.service_id,
                            iesc.events_of_period,
                            cmn.nus_id as user_id,
                            COALESCE(
                                array_agg(rel.product_id ORDER BY rel.product_id)
                                FILTER (WHERE rel.product_id IS NOT NULL),
                                ARRAY[]::integer[]
                            ) as subservice_array
                        FROM
                            ike_event_service_count_detail iesc
                            INNER JOIN custom_membership_nus cmn ON iesc.user_membership_id = cmn.id
                            LEFT JOIN {m2m_table} rel
                                ON iesc.id = rel.{m2m_detail_column}
                        GROUP BY
                            iesc.id,
                            iesc.user_membership_plan_id,
                            iesc.service_id,
                            iesc.events_of_period,
                            cmn.nus_id
                    ),
                    grouped_data AS (
                        SELECT
                            user_id,
                            user_membership_plan_id,
                            service_id,
                            subservice_array,
                            SUM(events_of_period) as total_events,
                            array_agg(detail_id ORDER BY detail_id) as detail_ids_array,
                            MIN(detail_id) as min_id
                        FROM
                            detail_subservices
                        GROUP BY
                            user_id,
                            user_membership_plan_id,
                            service_id,
                            subservice_array
                    )
                    SELECT
                        ROW_NUMBER() OVER (ORDER BY user_id, service_id, min_id) as id,
                        user_id,
                        user_membership_plan_id,
                        service_id,
                        total_events,
                        detail_ids_array::text as detail_ids_array,
                        subservice_array::text as subservice_array
                    FROM
                        grouped_data
                )
            """

            _logger.info("Ejecutando query...")
            self.env.cr.execute(query)

        # Eliminar tabla relacional si existe
        self.env.cr.execute("""
            DROP TABLE IF EXISTS ike_event_service_count_subservice_rel CASCADE;
        """)

        # Crear vista para la relación many2many
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW ike_event_service_count_subservice_rel AS (
                SELECT
                    esc.id as count_id,
                    unnest(
                        CASE
                            WHEN esc.subservice_array = '{}' OR esc.subservice_array IS NULL OR esc.subservice_array = ''
                                THEN ARRAY[]::integer[]
                            ELSE
                                string_to_array(trim(both '{}' from esc.subservice_array), ',')::integer[]
                        END
                    ) as product_id
                FROM
                    ike_event_service_count esc
                WHERE
                    esc.subservice_array IS NOT NULL
                    AND esc.subservice_array != '{}'
                    AND esc.subservice_array != ''
            )
        """)

        _logger.info("=== Vista ike_event_service_count creada exitosamente ===")


class CustomMembershipNus(models.Model):
    _inherit = 'custom.membership.nus'

    event_count_detail_ids = fields.One2many(
        'ike.event.service.count.detail',
        'user_membership_id',
        string='Event Details'
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super(CustomMembershipNus, self).create(vals_list)

        for record in records:
            event_lines = []
            if record.membership_plan_id:
                for service in record.membership_plan_id.product_line_ids:
                    event_lines.append((0, 0, {
                        'user_membership_plan_id': record.membership_plan_id.id if record.membership_plan_id else False,
                        'user_id': record.nus_id.id if record.nus_id else False,
                        'service_id': service.service_id.id if service.service_id else False,
                        'sub_service_ids': [(6, 0, service.sub_service_ids.ids)] if service.sub_service_ids else [],
                        'user_membership_id': record,
                        'vehicle_weight_category_id': service.vehicle_weight_category_id.id if service.vehicle_weight_category_id else False,
                        'date_start': record.membership_plan_id.contract_start_date,
                        'date_end': record.membership_plan_id.contract_end_date,
                        'coverage_events': service.period_per_event,
                        'period': service.period,
                        'status': True,
                    }))
            if event_lines:
                record.event_count_detail_ids = event_lines

        return records
