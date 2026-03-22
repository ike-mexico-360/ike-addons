from odoo import models, fields, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === FIELDS: SUPPLIER CENTER === #
    x_cost_matrix_line_ids = fields.One2many(
        'custom.supplier.cost.matrix.line', 'supplier_center_id',
        string='Cost Matrix')

    def action_cost_matrix_view(self):
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
            'domain': [('supplier_center_id', '=', self.id)],
            'views': [(False, 'list'), (False, 'form')],
        }
        if len(self.x_cost_matrix_line_ids) < 1:
            action['views'] = [(False, 'list')]
            action['res_id'] = self.x_cost_matrix_line_ids.id
        return action
