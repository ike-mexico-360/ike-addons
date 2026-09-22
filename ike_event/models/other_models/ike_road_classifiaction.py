from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class IkeRoadClassification(models.Model):
    _name = "ike.road.classification"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Help to road classification"

    name = fields.Char(string="Street", index='trigram')

    country_id = fields.Many2one(
        comodel_name='res.country',
        string='Country',
        required=True,
        index=True,
    )
    state_id = fields.Many2one(
        comodel_name='res.country.state',
        string='State',
        domain="[('country_id', '=', country_id)]",
        index=True,
    )
    destination_ids = fields.One2many(
        comodel_name='ike.road.classification_rel',
        inverse_name='origin_id',
        string='Destinations',
        context={'active_test': False}
    )

    active = fields.Boolean(default=True)
    disabled = fields.Boolean(default=False, tracking=True)

    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if not rec.name:
                continue

            existing = self.search([
                ('id', '!=', rec.id),
                ('name', '=ilike', rec.name.strip()),
            ], limit=1)

            if existing:
                raise ValidationError(
                    _("The name '%s' already exists. It must be unique.") % rec.name
                )


class IkeRoadClassificationRel(models.Model):
    _name = "ike.road.classification_rel"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Help to road classification relation"

    origin_id = fields.Many2one('ike.road.classification', required=True, index=True, ondelete='cascade')
    destination_id = fields.Many2one('ike.road.classification', required=True, index=True, ondelete='cascade')

    active = fields.Boolean(default=True)

    @api.model_create_multi
    def create(self, vals_list):
        inverse_list = []
        for vals in vals_list:
            inverse_list.append({
                'origin_id': vals['destination_id'],
                'destination_id': vals['origin_id'],
            })

        res = super().create(vals_list + inverse_list)

        return res

    def unlink(self):
        if self.env.context.get('skip_mirror_unlink'):
            return super().unlink()

        inverse_ids = self
        for rec in self:
            inverse_ids += self.search([
                ('origin_id', '=', rec.destination_id.id),
                ('destination_id', '=', rec.origin_id.id),
            ])

        res = super().unlink()

        if inverse_ids:
            inverse_ids.with_context(skip_mirror_unlink=True).unlink()

        return res

    def write(self, vals):
        if self.env.context.get('skip_mirror'):
            return super().write(vals)

        inverse_ids = self

        if 'active' in vals:
            Relation = self.with_context(active_test=False)

            for rec in self:
                inverse_ids |= Relation.search([
                    ('origin_id', '=', rec.destination_id.id),
                    ('destination_id', '=', rec.origin_id.id),
                ])

            inverse_ids -= self

        result = super().write(vals)

        if inverse_ids:
            inverse_ids.with_context(skip_mirror=True).write({
                'active': vals['active'],
            })

        return result
