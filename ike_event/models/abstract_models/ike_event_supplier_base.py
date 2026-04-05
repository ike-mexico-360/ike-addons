from odoo import models, fields, api, tools, _
from odoo.exceptions import AccessError


class IkeEventSupplierBase(models.AbstractModel):
    _name = 'ike.event.supplier.base'
    _description = 'Event Supplier Base'

    # Key Fields
    event_id = fields.Many2one('ike.event', required=True)
    event_stage_ref = fields.Char(related='event_id.stage_ref', string='Stage Ref')
    sequence = fields.Integer(default=5, required=True)
    folio = fields.Char(readonly=True, copy=False)
    name = fields.Text('Description')

    # Related fields
    supplier_id = fields.Many2one('res.partner', domain="[('x_is_supplier', '=', True)]")
    supplier_center_id = fields.Many2one('res.partner', readonly=True)
    service_ref = fields.Char(related="event_id.service_ref")
    subservice_id = fields.Many2one(related='event_id.sub_service_id')
    event_search_type = fields.Selection(related='event_id.supplier_search_type')

    # Flow fields
    state = fields.Selection([
        ('available', 'Available'),
        ('notified', 'Notified'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('timeout', 'Timeout'),
        ('expired', 'Expired'),
        ('assigned', 'Assigned'),
        ('unassigned', 'Unassigned'),
        ('cancel', 'Cancelled'),
        ('cancel_event', 'Cancelled by Event'),
        ('cancel_supplier', 'Cancelled by Supplier'),
    ], default='available', readonly=True, copy=False)
    stage_id = fields.Many2one('ike.service.stage', ondelete='set null', copy=False, tracking=True)
    stage_ref = fields.Char(related='stage_id.ref', string='Stage Ref')

    # Assignation supplier fields
    truck_id = fields.Many2one('fleet.vehicle', string='Service Vehicle')
    truck_plate = fields.Char(related='truck_id.license_plate')
    assigned = fields.Char(string='Assigned')
    assignation_type = fields.Selection([
        ('electronic', 'Electronic'),
        ('publication', 'Publication'),
        ('manual', 'Manual'),
        ('manual_manual', 'Manual Added'),
    ], default='manual', copy=False)

    # Manage state app notification
    notification_sent_to_app = fields.Boolean(string="Notification sent to app", default=False)
    supplier_link_id = fields.Many2one('ike.event.supplier.link')
