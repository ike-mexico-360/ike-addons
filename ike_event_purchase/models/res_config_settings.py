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
