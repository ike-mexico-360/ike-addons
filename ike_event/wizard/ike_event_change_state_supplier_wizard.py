import logging
import time
import requests
import threading
from datetime import timedelta


from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.modules.registry import Registry
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class IkeEventChangeStateSupplierWizard(models.TransientModel):
    _name = 'ike.event.change.state.supplier.wizard'
    _description = 'Event Change State Wizard'

    # === FIELDS SUPPLIER === #
    event_supplier_id = fields.Many2one(
        'ike.event.supplier',
        string='Supplier',
        required=True,
        readonly=True,
        ondelete='cascade'
    )
    event_id = fields.Many2one(related='event_supplier_id.event_id')
    stage_id = fields.Many2one(related='event_supplier_id.stage_id', string='Current state')

    first_state_date = fields.Datetime(string='First state datetime', readonly=True)
    first_state_user_id = fields.Many2one('res.users', string='First state user', readonly=True)
    first_comment = fields.Text(string='First comment', readonly=True)

    stage_selected = fields.Selection([
        ('arrived', 'Arrived'),
        ('contacted', 'Contacted'),
        ('finalized', 'Finalized'),
    ], string='Stage')

    supplier_assignation_date = fields.Datetime(
        readonly=True,
        string='Assigned')
    supplier_on_route_to_user_end_date = fields.Datetime(
        readonly=True,
        string='Arrived')
    supplier_contacted_date = fields.Datetime(
        readonly=True,
        string='Contacted')
    supplier_finalized_date = fields.Datetime(
        readonly=True,
        string='Finalized')

    # === ARRIVED ===
    first_on_route_to_user_end_date = fields.Datetime(
        string='Arrived (first datetime)', readonly=True)
    first_on_route_to_end_user_id = fields.Many2one(
        'res.users', string='Arrived (first user)', readonly=True)
    first_on_route_to_end_comment = fields.Text(
        string='Arrived (first comment)', readonly=True)

    on_route_to_user_end_date = fields.Datetime(string='Arrived (datetime)')
    on_route_to_end_user_id = fields.Many2one(
        'res.users',
        string='Arrived (user)'
    )
    on_route_to_end_comment = fields.Text(string='Arrived (comment)')

    # === CONTACTED ===
    first_contacted_date = fields.Datetime(
        string='Contacted (first datetime)', readonly=True)
    first_contacted_user_id = fields.Many2one(
        'res.users', string='Contacted (first user)', readonly=True)
    first_contacted_comment = fields.Text(
        string='Contacted (first comment)', readonly=True)

    contacted_date = fields.Datetime(string='Contacted (datetime)')
    contacted_user_id = fields.Many2one(
        'res.users',
        string='Contacted (user)'
    )
    contacted_comment = fields.Text(string='Contacted (comment)')

    # === FINALIZED ===
    first_finalized_date = fields.Datetime(
        string='Finalized (first datetime)', readonly=True)
    first_finalized_user_id = fields.Many2one(
        'res.users', string='Finalized (first user)', readonly=True)
    first_finalized_comment = fields.Text(
        string='Finalized (first comment)', readonly=True)

    finalized_date = fields.Datetime(string='Finalized (datetime)')
    finalized_user_id = fields.Many2one(
        'res.users',
        string='Finalized (user)'
    )
    finalized_comment = fields.Text(string='Finalized (comment)')

    # === COMPUTED FIELDS === #
    is_contacted_editable = fields.Boolean(compute='_compute_editable_fields')
    is_finalized_editable = fields.Boolean(compute='_compute_editable_fields')

    # === [MIGRACIÓN] TIME LOG HELPERS === #
    def _get_supplier_logs(self, supplier=None):
        """ time_log_ids del supplier (vacío si no hay supplier). """
        supplier = supplier if supplier is not None else self.event_supplier_id
        return supplier._origin.time_log_ids  # en onchange el registro puede venir como NewId

    def _get_stage_log(self, stage_key, is_first=False, supplier=None):
        """
        Devuelve el log (ike.event.supplier.time.log) de la etapa, o un recordset vacío.
        Con recordset vacío, log.date / log.user_id / log.comment devuelven False / vacío,
        igual que los campos viejos cuando no tenían valor.
          is_first=False -> equivale a <etapa>_date / _user_id / _comment
          is_first=True  -> equivale a first_<etapa>_date / _user_id / _comment
        time_log_ids viene ordenado por 'date desc, id desc', así que [:1] es el más reciente
        (el mismo resultado que el search(..., limit=1) anterior).
        """
        return self._get_supplier_logs(supplier).filtered(
            lambda log: log.stage_key == stage_key and log.is_first == is_first
        )[:1]

    def _has_stage_log(self, stage_key, supplier):
        """ Equivale a: bool(supplier.first_<etapa>_date or supplier.<etapa>_date) """
        return bool(self._get_supplier_logs(supplier).filtered(
            lambda log: log.stage_key == stage_key
        ))

    # [MIGRACIÓN] Campos informativos llenados al abrir el wizard (antes related al supplier)
    # campo_wizard: (stage_key, is_first, campo_del_log)
    _TIME_LOG_DEFAULTS = {
        'first_state_date': ('first_state', True, 'date'),
        'first_state_user_id': ('first_state', True, 'user_id'),
        'first_comment': ('first_state', True, 'comment'),

        'supplier_on_route_to_user_end_date': ('arrived', False, 'date'),
        'supplier_contacted_date': ('contacted', False, 'date'),
        'supplier_finalized_date': ('finalized', False, 'date'),

        'first_on_route_to_user_end_date': ('arrived', True, 'date'),
        'first_on_route_to_end_user_id': ('arrived', True, 'user_id'),
        'first_on_route_to_end_comment': ('arrived', True, 'comment'),

        'first_contacted_date': ('contacted', True, 'date'),
        'first_contacted_user_id': ('contacted', True, 'user_id'),
        'first_contacted_comment': ('contacted', True, 'comment'),

        'first_finalized_date': ('finalized', True, 'date'),
        'first_finalized_user_id': ('finalized', True, 'user_id'),
        'first_finalized_comment': ('finalized', True, 'comment'),
    }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        supplier = self.env['ike.event.supplier'].browse(res.get('event_supplier_id'))
        if not supplier:
            return res

        for fname, (stage_key, is_first, log_field) in self._TIME_LOG_DEFAULTS.items():
            if fname not in fields_list:
                continue
            log = self._get_stage_log(stage_key, is_first=is_first, supplier=supplier)
            value = log[log_field]
            res[fname] = value.id if log_field == 'user_id' else value

        if 'supplier_assignation_date' in fields_list:
            res['supplier_assignation_date'] = supplier._get_assignation_date()
        return res

    # === DEFAULT === #
    @api.depends('contacted_date', 'finalized_date')
    def _compute_editable_fields(self):
        for rec in self:
            rec.is_contacted_editable = bool(rec._get_stage_log('arrived').date)
            rec.is_finalized_editable = bool(rec._get_stage_log('contacted').date)

    # === METHODS ONCHANGE === #
    @api.onchange('stage_selected')
    def _onchange_stage(self):
        if self.stage_selected == 'arrived':
            log = self._get_stage_log('arrived')
            self.on_route_to_user_end_date = log.date
            self.on_route_to_end_user_id = log.user_id
            self.on_route_to_end_comment = log.comment

        elif self.stage_selected == 'contacted':
            if not self._get_stage_log('arrived').date:
                return {
                    'warning': {
                        'title': _('Contacted: Invalid datetime'),
                        'message': _(
                            'You must first register the Arrived datetime '
                            'before registering the Contacted datetime.')
                    }
                }

            log = self._get_stage_log('contacted')
            self.contacted_date = log.date
            self.contacted_user_id = log.user_id
            self.contacted_comment = log.comment

        elif self.stage_selected == 'finalized':
            if not self._get_stage_log('contacted').date:
                return {
                    'warning': {
                        'title': _('Finalized: Invalid datetime'),
                        'message': _(
                            'You must first register the Contacted datetime '
                            'before registering the Finalized datetime.')
                    }
                }

            log = self._get_stage_log('finalized')
            self.finalized_date = log.date
            self.finalized_user_id = log.user_id
            self.finalized_comment = log.comment

    # Arrived
    @api.onchange('on_route_to_user_end_date')
    def _onchange_on_route_to_user_end_date(self):

        if not self.on_route_to_user_end_date:
            return

        # [MIGRACIÓN] fechas actuales desde el log
        assignation_date = self.event_supplier_id._get_assignation_date()
        arrived_date = self._get_stage_log('arrived').date
        contacted_date = self._get_stage_log('contacted').date

        if (self.on_route_to_user_end_date != arrived_date):
            self.on_route_to_end_user_id = self.env.user.id
            self.on_route_to_end_comment = False

        if (
            (
                self.event_id.event_date
                and self.on_route_to_user_end_date <= self.event_id.event_date
            )
            or self.on_route_to_user_end_date > fields.Datetime.now()
        ):
            if self.on_route_to_user_end_date > fields.Datetime.now():
                message = _(
                    'The date and time of Arrived (%s) cannot be in the future.'
                ) % self._format_datetime_tz(self.on_route_to_user_end_date)
            else:
                message = _(
                    'The date and time of Arrived (%s) is less than or equal to '
                    'the date and time of the event (%s)'
                ) % (
                    self._format_datetime_tz(self.on_route_to_user_end_date),
                    self._format_datetime_tz(self.event_id.event_date)
                )

            return {
                'warning': {
                    'title': _('Arrived: Invalid datetime'),
                    'message': message,
                }
            }

        if (assignation_date and self.on_route_to_user_end_date <= assignation_date):
            return {
                'warning': {
                    'title': _('Arrived: Invalid datetime'),
                    'message': _(
                        'The date and time of Arrived (%s) is less than or equal to '
                        'the date and time of the Assigned (%s)'
                    ) % (
                        self._format_datetime_tz(self.on_route_to_user_end_date),
                        self._format_datetime_tz(assignation_date)
                    )
                }
            }
        elif contacted_date and self.on_route_to_user_end_date >= contacted_date:
            return {
                'warning': {
                    'title': _('Arrived: Invalid datetime'),
                    'message': _(
                        'The date and time of Arrived (%s) is greater than or equal to '
                        'the date and time of the Contacted (%s)',
                    ) % (
                        self._format_datetime_tz(self.on_route_to_user_end_date),
                        self._format_datetime_tz(contacted_date)
                    )
                }
            }

    # Contacted
    @api.onchange('contacted_date')
    def _onchange_contacted_date(self):

        if not self.contacted_date:
            return

        # [MIGRACIÓN] fechas actuales desde el log
        arrived_date = self._get_stage_log('arrived').date
        contacted_date = self._get_stage_log('contacted').date
        finalized_date = self._get_stage_log('finalized').date

        if (self.contacted_date != contacted_date):
            self.contacted_user_id = self.env.user.id
            self.contacted_comment = False

        if (
            (
                self.event_id.event_date
                and self.contacted_date <= self.event_id.event_date
            )
            or self.contacted_date > fields.Datetime.now()
        ):
            if self.contacted_date > fields.Datetime.now():
                message = _(
                    'The date and time of Contacted (%s) cannot be in the future.'
                ) % self._format_datetime_tz(self.contacted_date)
            else:
                message = _(
                    'The date and time of Contacted (%s) is less than or equal to '
                    'the date and time of the event (%s)'
                ) % (
                    self._format_datetime_tz(self.contacted_date),
                    self._format_datetime_tz(self.event_id.event_date)
                )

            return {
                'warning': {
                    'title': _('Contacted: Invalid datetime'),
                    'message': message,
                }
            }

        if (
            arrived_date
            and self.contacted_date <= arrived_date
        ):
            return {
                'warning': {
                    'title': _('Contacted: Invalid datetime'),
                    'message': _(
                        'The date and time of Contacted (%s) is less than or equal to '
                        'the date and time of the Arrived (%s)'
                    )
                    % (
                        self._format_datetime_tz(self.contacted_date),
                        self._format_datetime_tz(
                            arrived_date
                        ),
                    ),
                }
            }
        elif finalized_date and self.contacted_date >= finalized_date:
            return {
                'warning': {
                    'title': _('Contacted: Invalid datetime'),
                    'message': _(
                        'The date and time of Contacted (%s) is greater than or equal to '
                        'the date and time of the Finalized (%s)',
                    ) % (
                        self._format_datetime_tz(self.contacted_date),
                        self._format_datetime_tz(finalized_date)
                    )
                }
            }

    # Finalized
    @api.onchange('finalized_date')
    def _onchange_finalized_date(self):
        if not self.finalized_date:
            return

        # [MIGRACIÓN] fechas actuales desde el log
        contacted_date = self._get_stage_log('contacted').date
        finalized_date = self._get_stage_log('finalized').date

        if (self.finalized_date != finalized_date):
            self.finalized_user_id = self.env.user.id
            self.finalized_comment = False

        if (
            (
                self.event_id.event_date
                and self.finalized_date <= self.event_id.event_date
            )
            or self.finalized_date > fields.Datetime.now()
        ):
            if self.finalized_date > fields.Datetime.now():
                message = _(
                    'The date and time of Finalized (%s) cannot be in the future.'
                ) % self._format_datetime_tz(self.finalized_date)
            else:
                message = _(
                    'The date and time of Finalized (%s) is less than or equal to '
                    'the date and time of the event (%s)'
                ) % (
                    self._format_datetime_tz(self.finalized_date),
                    self._format_datetime_tz(self.event_id.event_date)
                )

            return {
                'warning': {
                    'title': _('Finalized: Invalid datetime'),
                    'message': message,
                }
            }

        if (contacted_date and self.finalized_date <= contacted_date):
            return {
                'warning': {
                    'title': _('Finalized: Invalid datetime'),
                    'message': _(
                        'The date and time of Finalized (%s) is less than or equal to '
                        'the date and time of the Contacted (%s)'
                    ) % (
                        self._format_datetime_tz(self.finalized_date),
                        self._format_datetime_tz(contacted_date))
                }
            }

    # === ACTION === #
    def action_confirm(self):
        self.ensure_one()
        if not self.stage_selected:
            raise ValidationError(_('Please select a stage.'))

        event_supplier = self.event_supplier_id
        vals = {}

        # [MIGRACIÓN] fechas actuales desde el log
        assignation_date = self.event_supplier_id._get_assignation_date()
        arrived_date = self._get_stage_log('arrived').date
        contacted_date = self._get_stage_log('contacted').date
        finalized_date = self._get_stage_log('finalized').date

        if self.stage_selected == 'arrived':
            self._validate_not_future(self.on_route_to_user_end_date, _('Arrived'))

            if self.on_route_to_user_end_date <= self.event_id.event_date:
                event_date = fields.Datetime.context_timestamp(self, self.event_id.event_date).strftime('%d-%m-%Y %H:%M:%S')
                raise ValidationError(_('Arrived date cannot be earlier than or equal to event date (%s)', event_date))
            else:
                if (
                    assignation_date
                    and self.on_route_to_user_end_date
                    <= assignation_date
                ):
                    raise ValidationError(
                        _(
                            'The date and time of Arrived (%s) is less than or equal to '
                            'the date and time of the Assigned (%s)',
                            self._format_datetime_tz(self.on_route_to_user_end_date),
                            self._format_datetime_tz(
                                assignation_date
                            ),
                        )
                    )
                elif (
                    contacted_date
                    and self.on_route_to_user_end_date
                    >= contacted_date
                ):
                    raise ValidationError(
                        _(
                            'The date and time of Arrived (%s) is greater than or equal to '
                            'the date and time of the Contacted (%s)',
                            self._format_datetime_tz(self.on_route_to_user_end_date),
                            self._format_datetime_tz(
                                contacted_date
                            ),
                        )
                    )
                else:
                    on_route_date = self.on_route_to_user_end_date - timedelta(seconds=1)
                    aux_tz_on_route_date = self._format_datetime_tz(on_route_date)
                    self._action_on_route(
                        event_supplier,
                        vals,
                        on_route_date,
                        self.on_route_to_end_user_id.id,
                        _(
                            'System - %(supplier)s - %(plate)s - %(datetime)s',
                            supplier=event_supplier.supplier_id.display_name,
                            plate=event_supplier.truck_plate or '',
                            datetime=aux_tz_on_route_date,
                        ),
                    )

                    time.sleep(
                        1
                    )  # Hack, no cambia a "En progreso" el evento si se ejecuta en cola, esperamos 1 segundo

                    self._action_arrived(
                        event_supplier,
                        vals,
                        self.on_route_to_user_end_date,
                        self.env.user.id,
                        self.on_route_to_end_comment,
                    )

        elif self.stage_selected == 'contacted':
            self._validate_not_future(self.contacted_date, _('Contacted'))

            if self.contacted_date <= self.event_id.event_date:
                event_date = fields.Datetime.context_timestamp(self, self.event_id.event_date).strftime('%d-%m-%Y %H:%M:%S')
                raise ValidationError(_('Contacted date cannot be earlier than or equal to event date (%s)', event_date))
            else:
                if (
                    arrived_date
                    and self.contacted_date
                    <= arrived_date
                ):
                    raise ValidationError(
                        _(
                            'The date and time of Contacted (%s) is less than or equal to '
                            'the date and time of the Arrived (%s)',
                            self._format_datetime_tz(self.contacted_date),
                            self._format_datetime_tz(
                                arrived_date
                            ),
                        )
                    )
                elif finalized_date and self.contacted_date >= finalized_date:
                    raise ValidationError(_(
                        'The date and time of Contacted (%s) is greater than or equal to '
                        'the date and time of the Finalized (%s)',
                        self._format_datetime_tz(self.contacted_date),
                        self._format_datetime_tz(finalized_date))
                    )
                else:
                    self._action_contacted(
                        event_supplier,
                        vals,
                        self.contacted_date,
                        self.contacted_user_id.id,
                        self.contacted_comment
                    )

        elif self.stage_selected == 'finalized':
            self._validate_not_future(self.finalized_date, _('Finalized'))

            if self.finalized_date <= self.event_id.event_date:
                event_date = fields.Datetime.context_timestamp(self, self.event_id.event_date).strftime('%d-%m-%Y %H:%M:%S')
                raise ValidationError(_('Finalized date cannot be earlier than or equal to event date (%s)', event_date))
            else:
                if contacted_date and self.finalized_date <= contacted_date:
                    raise ValidationError(_(
                        'The date and time of Finalized (%s) is less than or equal to '
                        'the date and time of the Contacted (%s)',
                        self._format_datetime_tz(self.finalized_date),
                        self._format_datetime_tz(contacted_date))
                    )
                else:
                    on_route_2_date = self.finalized_date - timedelta(seconds=2)
                    aux_tz_on_route_2_date = self._format_datetime_tz(on_route_2_date)

                    self._action_on_route_2(
                        event_supplier,
                        vals,
                        on_route_2_date,
                        self.finalized_user_id.id,
                        _(
                            'System - %(supplier)s - %(plate)s - %(datetime)s',
                            supplier=event_supplier.supplier_id.display_name,
                            plate=event_supplier.truck_plate or '',
                            datetime=aux_tz_on_route_2_date,
                        )
                    )

                    arrived_2_date = self.finalized_date - timedelta(seconds=1)
                    aux_tz_arrived_2_date = self._format_datetime_tz(arrived_2_date)

                    self._action_arrived_2(
                        event_supplier,
                        vals,
                        arrived_2_date,
                        self.finalized_user_id.id,
                        _(
                            'System - %(supplier)s - %(plate)s - %(datetime)s',
                            supplier=event_supplier.supplier_id.display_name,
                            plate=event_supplier.truck_plate or '',
                            datetime=aux_tz_arrived_2_date,
                        )
                    )

                    self._action_finalized(
                        event_supplier,
                        vals,
                        self.finalized_date,
                        self.finalized_user_id.id,
                        self.finalized_comment
                    )

        # [MIGRACIÓN] Antes: first_state_date / first_state_user_id / first_comment en vals
        if not self._get_stage_log('first_state', is_first=True, supplier=event_supplier):
            event_supplier._register_stage_time(
                stage_key='first_state',
                date_val=fields.Datetime.now(),
                user_id=self.env.user.id,
                comment=_(
                    f'User: {self.env.user.display_name}'
                    f' - Datetime: {self._format_datetime_tz(fields.Datetime.now())}'
                ),
            )

        event_supplier.write(vals)

        return event_supplier.open_change_state_supplier_wizard()

    def _format_datetime_tz(self, dt):
        if not dt:
            return ''
        local_dt = fields.Datetime.context_timestamp(self, dt)
        return local_dt.strftime('%d/%m/%Y %H:%M:%S')

    # [MIGRACIÓN] En todos los _action_*:
    #   - already_X: antes bool(first_X_date or X_date) -> existe log de la etapa
    #   - rama "ya existía": antes supplier.write({...}) -> _register_stage_time (actualiza el log actual)
    #   - rama "primera vez": antes vals.update({...}) -> _register_stage_time después de la acción
    #     (antes esos vals se escribían al final de action_confirm, también después de la acción)
    #   - Asignado no se registra desde este wizard (solo es informativo):
    #     la fecha la registra action_assign de ike.event.supplier.
    def _action_on_route(self, supplier, vals, datetime, user, comment):
        already_on_route = self._has_stage_log('on_route', supplier)

        if already_on_route:
            supplier._register_stage_time('on_route', datetime, user, comment)
            return

        first_date = self._get_stage_log('on_route', is_first=True, supplier=supplier).date or datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_on_route()

        supplier._register_stage_time('on_route', datetime, user, comment)

    def _action_arrived(self, supplier, vals, datetime, user, comment):
        already_arrived = self._has_stage_log('arrived', supplier)

        if already_arrived:
            supplier._register_stage_time('arrived', datetime, user, comment)
            return

        first_date = self._get_stage_log('arrived', is_first=True, supplier=supplier).date or datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_arrive()

        supplier._register_stage_time('arrived', datetime, user, comment)

        # Use here to ensure execute only on 'arrived' stage at first time
        self._notify_stage_change_to_external_supplier(supplier, datetime, 'llego', user, comment)

    def _action_contacted(self, supplier, vals, datetime, user, comment):
        already_contacted = self._has_stage_log('contacted', supplier)

        if already_contacted:
            supplier._register_stage_time('contacted', datetime, user, comment)
            return

        first_date = self._get_stage_log('contacted', is_first=True, supplier=supplier).date or datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_contact()

        supplier._register_stage_time('contacted', datetime, user, comment)

        # Use here to ensure execute only on 'contacted' stage at first time
        self._notify_stage_change_to_external_supplier(supplier, datetime, 'contactado', user, comment)

    def _action_on_route_2(self, supplier, vals, datetime, user, comment):
        already_on_route = self._has_stage_log('on_route_destination', supplier)

        if already_on_route:
            supplier._register_stage_time('on_route_destination', datetime, user, comment)
            return

        first_date = self._get_stage_log('on_route_destination', is_first=True, supplier=supplier).date or datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_on_route_to_the_destination()

        supplier._register_stage_time('on_route_destination', datetime, user, comment)

    def _action_arrived_2(self, supplier, vals, datetime, user, comment):
        already_arrived = self._has_stage_log('arrived_destination', supplier)

        if already_arrived:
            supplier._register_stage_time('arrived_destination', datetime, user, comment)
            return

        first_date = self._get_stage_log('arrived_destination', is_first=True, supplier=supplier).date or datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_arrive_to_the_destination()

        supplier._register_stage_time('arrived_destination', datetime, user, comment)

    def _action_finalized(self, supplier, vals, datetime, user, comment):
        already_finalized = self._has_stage_log('finalized', supplier)

        if already_finalized:
            supplier._register_stage_time('finalized', datetime, user, comment)
            return

        first_date = self._get_stage_log('finalized', is_first=True, supplier=supplier).date or datetime

        supplier.with_context(
            binnacle_first_date=first_date,
            binnacle_current_date=datetime,
            binnacle_comment=comment,
        ).action_finalize()

        supplier._register_stage_time('finalized', datetime, user, comment)

        # Use here to ensure execute only on 'finalized' stage at first time
        self._notify_stage_change_to_external_supplier(supplier, datetime, 'finalizado', user, comment)

    def _notify_stage_change_to_external_supplier(self, supplier, action_date, action_name, user_id, comment):
        # Send notification to external
        try:
            neutralized = self.env['ir.config_parameter'].sudo().get_param('database.is_neutralized')
            if neutralized:
                return

            if supplier.supplier_id.x_has_external_notification:
                db_name = self.env.cr.dbname
                record_ids = self.ids
                vehicle_uid = supplier.truck_id.x_vehicle_ref
                event_id = supplier.event_id.id
                action_date_str = action_date.strftime('%Y-%m-%d %H:%M:%S')
                # stages = dict(self._fields['stage_selected'].get_description(self.env)['selection'])
                action_name_str = action_name  # stages.get(action_name)
                responsible_name = self.env['res.users'].browse(user_id).name or ''

                @self.env.cr.postcommit.add
                def send_notifications_with_new_cursor():
                    threading.Thread(
                        target=self._async_send_notification,
                        args=(
                            db_name, record_ids, '_send_external_notifcation',
                            vehicle_uid, event_id, action_date_str, action_name_str, responsible_name, comment
                        ),
                        daemon=True,
                    ).start()
        except Exception as e:
            _logger.error('Error sending notification to external supplier: %s', e)

    def _send_external_notifcation(
            self, vehicle_uid: str, event_id: int, action_date: str, action_name: str, responsible_name: str, comment: str):
        external_url = self.env['ir.config_parameter'].sudo().get_param('ike_event.stage_change_external_notification_url')
        if not external_url:
            _logger.warning("No se ha configurado la URL de notificación a proveedores externos")
            return

        body = {
            "uuid_grua": vehicle_uid,
            "id_evento": event_id,
            "fecha_hora": action_date,
            "estado": action_name,
            "responsable": responsible_name,
            "comentario": comment
        }
        _logger.info(f"External notification at manual stage change (Body): {body}")
        external_response = requests.post(
            str(external_url),
            json=body,
            headers={
                "Content-Type": "application/json",
            }
        )
        if external_response:
            _logger.info(f"External notification at manual stage change (Response): {external_response.json()}")

    def _async_send_notification(self, db_name, record_ids, action_name, *args):
        """Thread to send notification"""
        db_registry = Registry(db_name)
        with db_registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})

            records = env['ike.event.change.state.supplier.wizard'].browse(record_ids).sudo()
            method = getattr(records, action_name, None)
            if callable(method):
                method(*args)

    def _validate_not_future(self, date_value, field_name):
        if not date_value:
            return

        now = fields.Datetime.now()

        if date_value > now:
            raise ValidationError(_(
                '%s date cannot be in the future'
            ) % (
                field_name
            ))
