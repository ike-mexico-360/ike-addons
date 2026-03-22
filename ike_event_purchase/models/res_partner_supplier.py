from dateutil.relativedelta import relativedelta
from datetime import date, timedelta
from odoo import models, fields, api
import logging
_logger = logging.getLogger(__name__)


class ResPartnerSupplier(models.Model):
    _inherit = 'res.partner'

    x_has_consolidation = fields.Boolean(
        string='Has Consolidation', default=False, tracking=True)

    x_consolidation_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Biweekly'),
        ('triweekly', 'Triweekly'),
        ('monthly', 'Monthly'),
    ], string='Consolidation Frequency', default='weekly', tracking=True)

    x_consolidation_day_of_week = fields.Selection([
        ('0', 'Sunday'),
        ('1', 'Monday'),
        ('2', 'Tuesday'),
        ('3', 'Wednesday'),
        ('4', 'Thursday'),
        ('5', 'Friday'),
        ('6', 'Saturday'),
    ], string='Day of Week', default='0', tracking=True)

    x_consolidation_day_of_month = fields.Integer(
        string='Day of Month', default=1, tracking=True)

    x_consolidation_next_date = fields.Date(
        string='Next Consolidation Date', tracking=True)

    # Mapeo de selección (0=Sunday) → weekday() de Python (0=Monday)
    # Sunday=0 → weekday()=6
    # Monday=1 → weekday()=0
    # ...
    _WEEKDAY_MAP = {
        '0': 6,  # Sunday
        '1': 0,  # Monday
        '2': 1,  # Tuesday
        '3': 2,  # Wednesday
        '4': 3,  # Thursday
        '5': 4,  # Friday
        '6': 5,  # Saturday
    }

    def _x_compute_next_consolidation_date(self):
        """Calcula y actualiza la próxima fecha de consolidación."""
        self.ensure_one()
        today = fields.Date.context_today(self)
        freq = self.x_consolidation_frequency

        if freq == 'daily':
            # Siempre el día siguiente
            next_date = today + timedelta(days=1)

        elif freq == 'monthly':
            day = min(self.x_consolidation_day_of_month, 28)
            next_date = today.replace(day=day)
            if next_date <= today:
                next_date = (today + relativedelta(months=1)).replace(day=day)

        else:
            delta_map = {'weekly': 7, 'biweekly': 14, 'triweekly': 21}
            delta_days = delta_map[freq]
            target_weekday = self._WEEKDAY_MAP[self.x_consolidation_day_of_week]

            _logger.warning(f"Today: {today} | target_weekday: {target_weekday} | {self.x_consolidation_day_of_week}")

            # Días hasta el próximo target_weekday
            days_ahead = (target_weekday - today.weekday()) % 7
            if days_ahead == 0:
                # Hoy es el día configurado, saltar al siguiente ciclo completo
                days_ahead = delta_days
            elif days_ahead > delta_days:
                # El día de la semana cae más lejos que el ciclo, ajustar
                days_ahead = days_ahead % delta_days or delta_days

            _logger.warning(f"days_ahead: {days_ahead}")

            next_date = today + timedelta(days=days_ahead)

        self.x_consolidation_next_date = next_date

    @api.onchange('x_has_consolidation', 'x_consolidation_frequency', 'x_consolidation_day_of_week', 'x_consolidation_day_of_month')
    def _onchange_consolidation_config(self):
        if self.x_has_consolidation and self.x_consolidation_frequency:
            self._x_compute_next_consolidation_date()

    @api.model
    def _x_cron_consolidate_orders(self):
        today = date.today()
        partners = self.env['res.partner'].search([
            ('x_has_consolidation', '=', True),
            ('x_consolidation_next_date', '<=', today),
        ])
        for partner in partners:
            orders = self.env['purchase.order'].search([
                ('partner_id', '=', partner.id),
                ('state', '=', 'to_consolidate'),
                ('x_dispute_state', '!=', 'open'),
            ])
            if orders:
                orders.x_action_consolidate()
            partner._x_compute_next_consolidation_date()
