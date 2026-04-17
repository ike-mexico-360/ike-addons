from odoo import models, fields, api, tools, _
from odoo.exceptions import AccessError


class IkeEventBase(models.AbstractModel):
    _name = 'ike.event.base'
    _description = 'Event Base'
    _order = 'id desc'

    name = fields.Char(
        'Expedient',
        required=True,
        readonly=True,
        index='trigram',
        copy=False,
        default=lambda self: _('New'))
    company_id = fields.Many2one(
        'res.company',
        required=True,
        readonly=True,
        index=True,
        default=lambda self: self.env.company)
    parent_id = fields.Many2one('ike.event', readonly=True, copy=False)

    # Flow fields
    stage_id = fields.Many2one('ike.event.stage', index=True, copy=False)
    stage_ref = fields.Char(related='stage_id.ref', string='Stage Reference')
    step_number = fields.Integer(default=1, copy=False)

    # Event fields
    event_date = fields.Datetime(string='Open Date', default=fields.Datetime.now, required=True)
    event_type_id = fields.Many2one('custom.type.event', string='Event Type')

    # nu fields
    user_id = fields.Many2one('custom.nus', readonly=False)

    # Service fields
    service_id = fields.Many2one('product.category')
    sub_service_id = fields.Many2one('product.product', 'Sub-Service')

    # Locations fields
    location_label = fields.Char()
    location_latitude = fields.Char()
    location_longitude = fields.Char()
    location_zip_code = fields.Char(size=10)
    destination_label = fields.Char()
    destination_latitude = fields.Char()
    destination_longitude = fields.Char()
    destination_zip_code = fields.Char(size=10)
