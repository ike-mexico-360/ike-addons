from odoo import _, api, fields, models
from markupsafe import Markup


class IkeEventServiceType(models.Model):
    _name = 'ike.event.service.type'
    _inherit = ['mail.thread']
    _description = 'Service type'
    _rec_name = 'name'

    name = fields.Char(string="Name", required=True, tracking=True, translate=True, default='New')
    service_id = fields.Many2one(
        'product.category',
        string='Service',
        domain="[('disabled', '=', False)]",
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    disabled = fields.Boolean(default=False, tracking=True)

    x_categ_domain = fields.Binary(string="Service domain", compute="_compute_x_categ_domain")

    @api.depends('name')
    def _compute_x_categ_domain(self):
        for rec in self:
            domain = []
            if rec._context.get('x_subservice_view', False):
                all_categ_id = self.env.ref('product.product_category_all')
                saleable_categ_id = self.env.ref('product.product_category_1')
                expense_categ_id = self.env.ref('product.cat_expense')
                domain = [('disabled', '=', False), ('id', 'not in', [all_categ_id.id, saleable_categ_id.id, expense_categ_id.id])]
            rec.x_categ_domain = domain
