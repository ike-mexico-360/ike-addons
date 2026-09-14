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
    # origin_ids = fields.One2many('ike.road.classification_rel', compute="")
    destination_ids = fields.One2many('ike.road.classification_rel', compute="_compute_destination_ids")

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

    @api.depends('destination_ids')
    def _compute_destination_ids(self):
        for rec in self:
            rec.destination_ids = self.env['ike.road.classification_rel'].search([
                '|',
                ('column_1_id', '=', rec.id),
                ('column_2_id', '=', rec.id),
            ])

    # @api.depends('origin_ids')
    # def _compute_destination_ids(self):
    #     for rec in self:
    #         rec.origin_ids = rec.origin_ids.search([
    #             '|',
    #             ('column_1_id', '=', rec.id),
    #             ('column_2_id', '=', rec.id),
    #         ])


class IkeRoadClassificationRel(models.Model):
    _name = "ike.road.classification_rel"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Help to road classification relation"

    column_1_id = fields.Many2one('ike.road.classification')
    column_2_id = fields.Many2one('ike.road.classification')

    active = fields.Boolean(default=True)
