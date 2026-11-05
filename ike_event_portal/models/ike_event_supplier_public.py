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

    def _x_ike_portal_line(self):
        """Real service line, only if the current user can see it (supplier / attention center)."""
        self.check_access('read')
        return self.env['ike.event.supplier'].sudo().browse(self.id)

    def action_accept(self):
        self._x_ike_portal_line().action_accept()

    def action_confirm_vehicle_portal(self):
        self._x_ike_portal_line().action_confirm_vehicle_portal()

    def action_notify_operator(self):
        self._x_ike_portal_line().action_notify_operator()

    def action_assign(self):
        self._x_ike_portal_line().action_assign()

    def get_event_supplier_summary_data(self):
        return self._x_ike_portal_line().event_supplier_summary_data

    def get_event_supplier_summary_data_portal(self):
        return self._x_ike_portal_line().event_supplier_summary_data_portal

    def get_travel_tracking_url(self):
        return self._x_ike_portal_line().travel_tracking_url

    def action_supplier_cancel(self, cancel_reason_id=None, reason_text=None):
        return self._x_ike_portal_line().action_supplier_cancel(
            cancel_reason_id=cancel_reason_id,
            reason_text=reason_text
        )

    def action_reject(self):
        self._x_ike_portal_line().action_reject()

    def get_selectable_vehicles(self):
        vehicles = self._x_ike_portal_line().get_selectable_vehicles()
        center_ids = self.env.user.x_ike_portal_center_ids()
        if center_ids:
            allowed_ids = self.env['fleet.vehicle'].sudo().search([
                ('id', 'in', [vehicle['id'] for vehicle in vehicles]),
                ('x_center_id', 'in', center_ids),
            ]).ids
            vehicles = [vehicle for vehicle in vehicles if vehicle['id'] in allowed_ids]
        return vehicles

    def action_change_service_vehicle(self, service_vehicle_id):
        record = self._x_ike_portal_line()
        vehicle = self.env['fleet.vehicle'].sudo().browse(service_vehicle_id)
        if not vehicle.exists():
            raise ValidationError(_('Invalid vehicle.'))
        if vehicle.x_partner_id.id != record.supplier_id.id:
            raise ValidationError(_('The selected vehicle does not belong to this supplier.'))
        center_ids = self.env.user.x_ike_portal_center_ids()
        if center_ids and vehicle.x_center_id.id not in center_ids:
            raise ValidationError(_('Invalid vehicle.'))
        return record.action_change_service_vehicle(vehicle.id)
    # ToDo
    # def write(self, vals):
    #     fields_names = list(vals.keys())
    #     event = self.env["ike.event.supplier"].sudo().browse(self.id)
    #     event._check_private_fields(fields_names)
    #     event.write(vals)
    #     return True
