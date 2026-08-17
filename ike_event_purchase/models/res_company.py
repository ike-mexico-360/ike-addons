from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_time_for_automatic_purchase_generation = fields.Integer(
        string="Time for automatic purchase generation", default=72,
        help="Waiting time to automatically approve the quote")

    x_display_po_summary_portal = fields.Boolean(
        string="Display Purchase Orders Summary Cards in Portal",
        default=False,
        help="Company-specific setting to display summary cards on the portal."
    )

    x_max_lines_per_po_at_consolidation = fields.Integer(
        string="Max lines per purchase order at consolidation",
        default=50,
        help="Technical: Max lines per purchase order at consolidation. If the number of lines is greater than this value, the purchase order will be splitted."
    )

    x_default_purchase_project_id = fields.Many2one(
        comodel_name='project.project',
        string='Default Purchase Project',
        help="Technical: Default purchase project linked to the company at consolidate and send SAP data.",
        ondelete='restrict',
        tracking=True,
    )

    @api.model
    def _ike_sync_helpdesk_dashboard_stages(self):
        """Display operational helpdesk stages on both dashboard sections."""
        excluded_stages = self.env["helpdesk.stages"].browse([
            self.env.ref("sh_all_in_one_helpdesk.cancel_stage").id,
            self.env.ref("sh_all_in_one_helpdesk.reopen_stage").id,
        ])
        stage_ids = self.env["helpdesk.stages"].search(
            [("id", "not in", excluded_stages.ids)], order="sequence, id"
        ).ids
        if stage_ids:
            self.search([]).write({
                "dashboard_filter": [(6, 0, stage_ids)],
                "dashboard_tables": [(6, 0, stage_ids)],
            })
