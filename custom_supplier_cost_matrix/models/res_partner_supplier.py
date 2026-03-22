from odoo import models, fields, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_cost_matrix_supplier_count = fields.Integer(
        string='Number cost matrix',
        compute='_compute_cost_matrix_supplier_count',
        store=False
    )

    def _compute_cost_matrix_supplier_count(self):
        for rec in self:
            count = self.x_supplier_center_ids.x_cost_matrix_line_ids
            rec.x_cost_matrix_supplier_count = count and len(count) or 0

    def action_cost_matrix_supplier_from_supplier_center_view(self):
        self.ensure_one()
        action = {
            'name': _('Matriz de costos'),
            'view_mode': 'list,form',
            'res_model': 'custom.supplier.cost.matrix.line',
            'context': {
                **self.env.context,
                'create': True,
                'default_supplier_center_id': self.id,
                'search_default_filter_enabled': 1,
            },
            'view_id': False,
            'type': 'ir.actions.act_window',
            'domain': [('id', 'in', self.x_supplier_center_ids.x_cost_matrix_line_ids.ids)],
            'views': [(False, 'list'), (False, 'form')],
        }
        if len(self.x_supplier_center_ids.x_cost_matrix_line_ids) < 1:
            action['views'] = [(False, 'list')]
            action['res_id'] = self.x_supplier_center_ids.x_cost_matrix_line_ids.id
        return action
