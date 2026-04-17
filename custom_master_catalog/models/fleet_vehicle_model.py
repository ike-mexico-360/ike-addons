from odoo import api, models, fields, _
from odoo.exceptions import ValidationError
from markupsafe import Markup


class FleetVehicleModel(models.Model):
    _inherit = 'fleet.vehicle.model'

    active = fields.Boolean('Active', default=True, tracking=True)
    disabled = fields.Boolean('Disabled', default=False, tracking=True)

    x_vehicle_weight_category_id = fields.Many2one(
        'custom.vehicle.weight.category',
        'Weight Category',
        domain="[('disabled', '=', False)]",
        tracking=True)
    x_category_id = fields.Many2one(
        'fleet.vehicle.model.category',
        string="Vehicle category",
        domain="[('disabled', '=', False)]")
    x_weigth = fields.Float(string="Vehicle weight", digits=(16, 2))
    x_length = fields.Float(string="Vehicle length", digits=(16, 2))
    x_high_value = fields.Boolean(string="High Value")
    x_connectable = fields.Boolean(string="Connectable")

    @api.constrains('name', 'brand_id')
    def _check_unique_vehicle_model(self):
        for rec in self:
            domain = [('name', '=', rec.name), ('brand_id', '=', rec.brand_id.id), ('id', '<>', rec.id)]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_('A vehicle model with the same name already exists.'))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_('A vehicle model with the same name already exists. It is disabled.'))

    def action_disable(self, reason=None):
        for rec in self:
            if reason:
                body = Markup("""
                    <ul class="mb-0 ps-4">
                        <li>
                            <b>{}: </b><span class="">{}</span>
                        </li>
                    </ul>
                """).format(
                    _('Disabled'),
                    reason,
                )
                rec.message_post(
                    body=body,
                    message_type='notification',
                    body_is_html=True)
        return super().action_disable(reason)
