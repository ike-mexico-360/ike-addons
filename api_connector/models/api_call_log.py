from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class ApiCallLog(models.Model):
    _name = 'api.call.log'
    _description = 'API Call Log'
    _order = 'call_date desc'
    _rec_name = 'display_name'

    connector_id = fields.Many2one(
        'api.connector',
        string='API Connection',
        required=True,
        ondelete='cascade'
    )

    success = fields.Boolean(
        string='Success',
        default=False,
        help='Whether the API call was successful'
    )

    status_code = fields.Integer(
        string='HTTP Status Code',
        help='HTTP response status code'
    )

    call_date = fields.Datetime(
        string='Call Date',
        default=fields.Datetime.now,
        required=True
    )

    execution_time = fields.Float(
        string='Execution Time (s)',
        help='Time taken to execute the API call in seconds'
    )

    request_data = fields.Text(
        string='Request Data',
        help='JSON representation of the request data sent'
    )

    response_data = fields.Text(
        string='Response Data',
        help='Response data received from the API'
    )

    error_message = fields.Text(
        string='Error Message',
        help='Error message if the call failed'
    )

    # === COMPUTED FIELDS ===
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )

    status_icon = fields.Char(
        string='Status Icon',
        compute='_compute_status_icon'
    )

    response_size = fields.Integer(
        string='Response Size (bytes)',
        compute='_compute_response_size'
    )

    @api.depends('connector_id', 'call_date', 'success')
    def _compute_display_name(self):
        """Compute display name for the log entry"""
        for record in self:
            connector_name = record.connector_id.name or 'Unknown'
            date_str = record.call_date.strftime('%Y-%m-%d %H:%M:%S') if record.call_date else 'Unknown'
            status = 'SUCCESS' if record.success else 'FAILED'
            record.display_name = f"{connector_name} - {date_str} - {status}"

    @api.depends('success', 'status_code')
    def _compute_status_icon(self):
        """Compute status icon based on success and status code"""
        for record in self:
            if record.success:
                if record.status_code == 200:
                    record.status_icon = '✅'
                elif record.status_code in [201, 202, 204]:
                    record.status_icon = '✅'
                else:
                    record.status_icon = '⚠️'
            else:
                if record.status_code and record.status_code >= 400:
                    if record.status_code < 500:
                        record.status_icon = '❌'  # Client error
                    else:
                        record.status_icon = '💥'  # Server error
                else:
                    record.status_icon = '🔴'  # Connection/timeout error

    @api.depends('response_data')
    def _compute_response_size(self):
        """Compute response data size in bytes"""
        for record in self:
            if record.response_data:
                record.response_size = len(record.response_data.encode('utf-8'))
            else:
                record.response_size = 0

    def get_formatted_request_data(self):
        """Get formatted request data for display"""
        self.ensure_one()
        if not self.request_data:
            return _('No request data')

        try:
            data = json.loads(self.request_data)
            return json.dumps(data, indent=2)
        except (json.JSONDecodeError, TypeError):
            return self.request_data

    def get_formatted_response_data(self):
        """Get formatted response data for display"""
        self.ensure_one()
        if not self.response_data:
            return _('No response data')

        try:
            data = json.loads(self.response_data)
            return json.dumps(data, indent=2)
        except (json.JSONDecodeError, TypeError):
            return self.response_data

    def action_view_details(self):
        """Open detailed view of the log entry"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('API Call Details'),
            'res_model': 'api.call.log',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_retry_call(self):
        """Retry the API call with the same parameters"""
        self.ensure_one()

        if not self.connector_id.active:
            raise UserError(_("Cannot retry call: API connection '%s' is not active") % self.connector_id.name)

        try:
            # Parse request data
            dynamic_data = None
            if self.request_data:
                try:
                    dynamic_data = json.loads(self.request_data)
                except json.JSONDecodeError:
                    pass

            # Execute the call
            result = self.connector_id.execute_call(dynamic_data)

            if result.get('success'):
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Retry Successful'),
                        'message': _('API call retried successfully'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Retry Failed'),
                        'message': result.get('error', 'Unknown error'),
                        'type': 'warning',
                        'sticky': True,
                    }
                }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Retry Error'),
                    'message': str(e),
                    'type': 'danger',
                    'sticky': True,
                }
            }

    @api.model
    def cleanup_old_logs(self, days=30):
        """Cleanup old log entries (called by cron)"""
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)
        old_logs = self.search([('call_date', '<', cutoff_date)])

        if old_logs:
            count = len(old_logs)
            old_logs.unlink()
            _logger.info(f"Cleaned up {count} old API call logs older than {days} days")

        return True

    @api.model
    def get_statistics(self, connector_id=None, days=7):
        """Get API call statistics"""
        from datetime import datetime, timedelta

        domain = []
        if connector_id:
            domain.append(('connector_id', '=', connector_id))

        # Filter by date range
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            domain.append(('call_date', '>=', cutoff_date))

        logs = self.search(domain)

        total_calls = len(logs)
        success_calls = len(logs.filtered('success'))
        failed_calls = total_calls - success_calls

        # Calculate average execution time
        avg_execution_time = 0
        if logs.filtered('execution_time'):
            avg_execution_time = sum(logs.mapped('execution_time')) / len(logs.filtered('execution_time'))

        # Success rate
        success_rate = (success_calls / total_calls) if total_calls > 0 else 0

        return {
            'total_calls': total_calls,
            'success_calls': success_calls,
            'failed_calls': failed_calls,
            'success_rate': success_rate,
            'avg_execution_time': avg_execution_time,
            'period_days': days
        }
