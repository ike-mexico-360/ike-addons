from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    x_time_for_automatic_purchase_generation = fields.Integer(
        related='company_id.x_time_for_automatic_purchase_generation',
        string="Time for automatic purchase generation",
        help="Waiting time to automatically approve the quote",
        readonly=False)

    x_display_po_summary_portal = fields.Boolean(
        related='company_id.x_display_po_summary_portal',
        readonly=False,
        string="Portal Summary Cards",
        help="If checked, summary cards with total amounts will be displayed on the portal's purchase orders list view for the active company."
    )

    x_max_lines_per_po_at_consolidation = fields.Integer(
        related='company_id.x_max_lines_per_po_at_consolidation',
        string="Max lines per purchase order at consolidation",
        default=50,
        help="Technical: Max lines per purchase order at consolidation. If the number of lines is greater than this value, the purchase order will be splitted.",
        readonly=False,
    )

    x_default_purchase_project_id = fields.Many2one(
        comodel_name='project.project',
        required=True,
        related='company_id.x_default_purchase_project_id',
        string='Default Purchase Project',
        help="Technical: Default purchase project linked to the company at consolidate and send SAP data.",
        ondelete='restrict',
        readonly=False,
    )
