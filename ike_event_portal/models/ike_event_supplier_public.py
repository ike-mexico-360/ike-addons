from odoo import models, fields, api, tools, _
from odoo.exceptions import AccessError, ValidationError


class IkeEventSupplierPublic(models.Model):
    _name = 'ike.event.supplier.public'
    _inherit = ['ike.event.supplier.base']
    _description = 'Event supplier (public)'
    _auto = False
    _log_access = True

    @api.model
    def _get_fields(self):
        return ','.join(
            'event_supplier.%s' % name
            for name, field in self._fields.items()
            if field.store and field.type not in ['many2many', 'one2many'])

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
            SELECT
                %s
            FROM ike_event_supplier event_supplier
        )""" % (self._table, self._get_fields()))

    def action_accept(self):
        self.env['ike.event.supplier'].sudo().browse(self.id).action_accept()

    def action_notify_operator(self):
        self.env['ike.event.supplier'].sudo().browse(self.id).action_notify_operator()

    def get_event_supplier_summary_data(self):
        return self.env['ike.event.supplier'].sudo().browse(self.id).event_supplier_summary_data

    def get_travel_tracking_url(self):
        return self.env['ike.event.supplier'].sudo().browse(self.id).travel_tracking_url

    def action_supplier_cancel(self, cancel_reason_id=None, reason_text=None):
        return self.env['ike.event.supplier'].sudo().browse(self.id).action_supplier_cancel(cancel_reason_id=cancel_reason_id, reason_text=reason_text)

    def action_reject(self):
        self.env['ike.event.supplier'].sudo().browse(self.id).action_reject()

    def get_selectable_vehicles(self):
        return self.env['ike.event.supplier'].sudo().browse(self.id).get_selectable_vehicles()

    def action_change_service_vehicle(self, service_vehicle_id):
        record = self.env['ike.event.supplier'].sudo().browse(self.id)
        vehicle = self.env['fleet.vehicle'].sudo().browse(service_vehicle_id)
        if not vehicle.exists():
            raise ValidationError(_('Invalid vehicle.'))
        if vehicle.x_partner_id.id != record.supplier_id.id:
            raise ValidationError(_('The selected vehicle does not belong to this supplier.'))
        return record.action_change_service_vehicle(vehicle.id)
    # ToDo
    # def write(self, vals):
    #     fields_names = list(vals.keys())
    #     event = self.env["ike.event.supplier"].sudo().browse(self.id)
    #     event._check_private_fields(fields_names)
    #     event.write(vals)
    #     return True
