from odoo import models, fields, api


class ResPartnerSupplierDriversRel(models.Model):
    _name = 'res.partner.supplier_drivers.rel'
    _description = 'Relation between Suppliers and Drivers'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    driver_id = fields.Many2one(
        'res.partner', string='Driver', ondelete='cascade', tracking=True, required=True, copy=False)
    user_ids = fields.Many2many('res.users', string='Users', compute='_compute_user_ids')
    center_of_attention_id = fields.Many2one(
        'res.partner', string='Center of Attention', ondelete='cascade', tracking=True, required=True, copy=True)
    supplier_id = fields.Many2one(
        'res.partner', string='Supplier', ondelete='cascade', tracking=True, required=True,
        domain=[('x_is_supplier', '=', True)], copy=True, compute='_compute_supplier_id', store=True)
    drivers_domain = fields.Binary(string='Drivers Domain', compute='_compute_drivers_domain')

    @api.depends('driver_id', 'supplier_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.driver_id.name} - {rec.supplier_id.name}"

    def _x_ike_get_operator_groups(self):
        # Obtener el ID del grupo de portal
        portal_group = self.env.ref('base.group_portal')
        return [portal_group.id]

    @api.depends('driver_id')
    def _compute_drivers_domain(self):
        for rec in self:
            # Todo: Qué otro filtro determinará a un operador?
            operator_groups = self._x_ike_get_operator_groups()
            domain = [
                ('user_ids', '!=', False),
                ('x_is_supplier', '=', False),
                ('disabled', '=', False),
                ('user_ids.groups_id', 'in', operator_groups)
            ]
            # Excluir conductores ya asignados
            self.env.cr.execute("""
                SELECT driver_id AS id
                FROM res_partner_supplier_drivers_rel;
            """)
            drivers = [x['id'] for x in self.env.cr.dictfetchall()]
            if len(drivers) > 0:
                domain.append(('id', 'not in', drivers))
            rec.drivers_domain = domain

    @api.depends('driver_id')
    def _compute_user_ids(self):
        for rec in self:
            rec.user_ids = rec.driver_id.user_ids.ids

    @api.depends('center_of_attention_id')
    def _compute_supplier_id(self):
        for rec in self:
            rec.supplier_id = rec.center_of_attention_id.parent_id.id
