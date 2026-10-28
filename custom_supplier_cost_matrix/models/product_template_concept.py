from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_matrix_workflow = fields.Selection(
        [('section_in_agreement', 'Section in agreement'), ('plan', 'Plan')],
        string="Matrix workflow",
        tracking=True,
        default='',
        compute="_compute_x_matrix_workflow",
        inverse="_inverse_x_matrix_workflow",
        store=True,
        help="empty: default workflow\nSection in agreement: Required origin an destination entity, municiplaity\nPlan: Required initial and final kilometers"
    )

    @api.depends('x_additional_ok')
    def _compute_x_matrix_workflow(self):
        for rec in self:
            if rec.x_additional_ok:
                rec.x_matrix_workflow = False

    def _inverse_x_matrix_workflow(self):
        pass
