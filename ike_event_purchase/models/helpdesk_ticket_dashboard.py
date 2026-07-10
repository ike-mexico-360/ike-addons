from odoo import api, fields, models


class TicketDashboard(models.Model):
    _inherit = "ticket.dashboard"

    def _format_dashboard_datetime(self, value):
        if not value:
            return ""
        timezone = self.env.context.get("tz") or self.env.user.tz or "America/Mexico_City"
        return fields.Datetime.context_timestamp(
            self.with_context(tz=timezone), value
        ).strftime("%Y-%m-%d %H:%M:%S")

    @api.model
    def get_ticket_table_data(
        self, team_leader, team, assign_user, filter_date,
        start_date, end_date, limit, offset, stage_id
    ):
        data = super().get_ticket_table_data(
            team_leader, team, assign_user, filter_date,
            start_date, end_date, limit, offset, stage_id
        )
        for stage_data in data:
            for ticket_data in stage_data.get("ticket_data", []):
                if ticket_data:
                    ticket_data[3] = self._format_dashboard_datetime(ticket_data[3])
                    ticket_data[4] = self._format_dashboard_datetime(ticket_data[4])
        return data
