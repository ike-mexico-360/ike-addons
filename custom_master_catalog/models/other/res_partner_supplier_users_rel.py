from odoo import models, fields, api


class ResPartnerSupplierUsersRel(models.Model):
    _name = 'res.partner.supplier_users.rel'
    _description = 'Relation between Suppliers and Users'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    user_id = fields.Many2one(
        'res.users', string='User', ondelete='cascade', tracking=True, required=True, copy=False)
    partner_id = fields.Many2one(
        'res.partner', related='user_id.partner_id', string='Partner', ondelete='cascade', tracking=True,
        copy=False, store=True)
    user_type = fields.Selection(
        selection=[
            ('operator', 'Operator'),
            ('supervisor', 'Supervisor'),
            ('administrator', 'Administrator'),
        ], string='User Type', required=True, default='operator')
    center_of_attention_id = fields.Many2one(
        'res.partner', string='Center of Attention', ondelete='cascade', tracking=True, required=True, copy=True)
    supplier_id = fields.Many2one(
        'res.partner', string='Supplier', ondelete='cascade', tracking=True,
        domain=[('x_is_supplier', '=', True)], copy=True, compute='_compute_supplier_id', store=True)
    users_domain = fields.Binary(string='Users Domain', compute='_compute_users_domain')

    @api.depends('user_id', 'supplier_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.user_id.name} - {rec.supplier_id.name}"

    def _x_ike_get_operator_groups(self):
        # Obtener el ID del grupo de portal
        portal_group = self.env.ref('base.group_portal')
        return [portal_group.id]

    @api.depends('user_id')
    def _compute_users_domain(self):
        for rec in self:
            # Todo: Qué otro filtro determinará a un operador?
            # Obtener el ID del grupo de portal
            operator_groups = self._x_ike_get_operator_groups()
            domain = [
                ('partner_id.x_is_supplier', '=', False),
                ('user_ids.groups_id', 'in', operator_groups)
            ]
            # Excluir conductores ya asignados
            self.env.cr.execute("""
                SELECT user_id AS id
                FROM res_partner_supplier_users_rel;
            """)
            users = [x['id'] for x in self.env.cr.dictfetchall()]
            if len(users) > 0:
                domain.append(('id', 'not in', users))
            rec.users_domain = domain

    @api.depends('center_of_attention_id')
    def _compute_supplier_id(self):
        for rec in self:
            rec.supplier_id = rec.center_of_attention_id.parent_id.id
