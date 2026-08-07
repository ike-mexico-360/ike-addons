# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ShHelpdeskTicketAssignmentWizard(models.TransientModel):
    _name = "sh.helpdesk.ticket.assignment.wizard"
    _description = "Ticket assignment wizard"

    assigned_user_ids = fields.Many2many("res.users", string="Assigned to users")
    assigned_user_id = fields.Many2one("res.users", string="Assigned to user")
    assigned_user_domain = fields.Binary(compute="_compute_assigned_user_domain")
    stage_id = fields.Many2one("helpdesk.stages", string="Stage")
    ticket_not_assign_ids = fields.Many2many(
        "sh.helpdesk.ticket",
        "sh_helpdesk_ticket_assignment_wizard_not_assign_rel",
        "wizard_id",
        "ticket_id",
        string="Tickets not assigned",
        domain=[("user_id", "=", False)],
    )
    ticket_assign_ids = fields.Many2many(
        "sh.helpdesk.ticket",
        "sh_helpdesk_ticket_assignment_wizard_assign_rel",
        "wizard_id",
        "ticket_id",
        string="Tickets assigned",
        compute="_compute_ticket_assign_ids",
    )

    @api.depends("assigned_user_ids", "assigned_user_id")
    def _compute_assigned_user_domain(self):
        group_xmlids = [
            "custom_master_catalog.custom_group_ccc_coordinator",
            "custom_master_catalog.custom_group_ccc_analyst",
            "custom_master_catalog.custom_group_ccc_boss",
        ]
        groups = [
            self.env.ref(xmlid).id
            for xmlid in group_xmlids
            if self.env.ref(xmlid, raise_if_not_found=False)
        ]
        for rec in self:
            rec.assigned_user_domain = [
                ("active", "=", True),
                ("groups_id", "in", groups),
            ]

    @api.depends("assigned_user_ids")
    def _compute_ticket_assign_ids(self):
        for rec in self:
            if rec.assigned_user_ids:
                rec.ticket_assign_ids = self.env["sh.helpdesk.ticket"].search([
                    ("user_id", "in", rec.assigned_user_ids.ids),
                ])
            else:
                rec.ticket_assign_ids = False

    def action_assignment_ticket(self):
        if not self.assigned_user_id:
            return
        if not self.stage_id:
            raise UserError(_("You must select a destination stage."))

        team = self.env["sh.helpdesk.team"].search([
            "|",
            ("team_members", "in", self.assigned_user_id.id),
            ("team_head", "=", self.assigned_user_id.id),
        ], order="id desc", limit=1)
        if not team:
            raise UserError(_("The assigned user must belong to a helpdesk team."))

        values = {
            "user_id": self.assigned_user_id.id,
            "team_id": team.id,
            "team_head": team.team_head.id,
            "stage_id": self.stage_id.id,
        }
        for ticket in self.ticket_not_assign_ids:
            ticket.with_context(ike_assignment_wizard=True).sudo().write(values)
