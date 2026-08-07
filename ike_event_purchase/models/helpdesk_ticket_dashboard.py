from datetime import datetime

from odoo import api, fields, models


class TicketDashboard(models.Model):
    _inherit = "ticket.dashboard"

    def _build_dashboard_domain(
        self, team_leader=False, team=False, assign_user=False,
        filter_date=False, start_date=False, end_date=False, stage_id=False,
        only_current_user=False,
    ):
        domain = []
        if team_leader:
            domain.append(("team_head", "=", team_leader))
        if team:
            domain.append(("team_id", "=", team))
        if assign_user:
            domain.append(("user_id", "=", assign_user))
        if stage_id:
            domain.append(("stage_id", "=", stage_id))
        if only_current_user:
            domain.append(("user_id", "=", self.env.user.id))

        if filter_date == "custom" and not (start_date and end_date):
            start_date = end_date = False
        elif filter_date and filter_date != "custom":
            start_date, end_date = self.generate_start_end_date(option=filter_date)

        if isinstance(start_date, str) and isinstance(end_date, str):
            start_date = datetime.strptime(start_date, "%m/%d/%Y").replace(
                hour=0, minute=0, second=0
            )
            end_date = datetime.strptime(end_date, "%m/%d/%Y").replace(
                hour=23, minute=59, second=59
            )
        if start_date and end_date:
            domain += [
                ("create_date", ">=", start_date),
                ("create_date", "<=", end_date),
            ]
        return domain

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
        stage_order = {
            stage.id: index
            for index, stage in enumerate(self.env.company.dashboard_tables)
        }
        data.sort(
            key=lambda stage_data: stage_order.get(
                stage_data["stage_id"], len(stage_order)
            )
        )
        for stage_data in data:
            for ticket_data in stage_data.get("ticket_data", []):
                if ticket_data:
                    ticket_data[3] = self._format_dashboard_datetime(ticket_data[3])
                    ticket_data[4] = self._format_dashboard_datetime(ticket_data[4])
        return data

    @api.model
    def get_ticket_counter_data(
        self, team_leader, team, assign_user, filter_date, start_date, end_date
    ):
        data, color_dict = super().get_ticket_counter_data(
            team_leader, team, assign_user, filter_date, start_date, end_date
        )
        counters = {}
        for stage_name, values in data.items():
            all_ids = values[0] if values else []
            stage = self.env["helpdesk.stages"].search(
                [("name", "=", stage_name)], limit=1
            )
            my_ids = []
            if stage:
                domain = self._build_dashboard_domain(
                    team_leader, team, assign_user, filter_date,
                    start_date, end_date, stage.id, only_current_user=True
                )
                my_ids = self.env["sh.helpdesk.ticket"].search(domain).ids
            counters[stage_name] = [all_ids, my_ids]
        return counters, color_dict
