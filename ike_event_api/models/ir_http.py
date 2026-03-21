from odoo import models
# from odoo.http import request
# from odoo.tools import html2plaintext


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        session_info = super().session_info()
        user = self.env.user

        # Si es usuario interno y tiene permiso de lectura
        if (user._is_internal() or user._is_portal()):
            self.env.cr.execute("""
                SELECT
                    fv.id
                    ,fv.x_vehicle_ref
                    ,fv.name
                    ,rps.id AS supplier_id
                    ,rps.name AS supplier_name
                    ,rp.id AS driver_id
                    ,rp.name AS driver_name
                    ,ca.id AS ca_id
                    ,ca.name AS ca_name
                    ,fv.brand_id
                    ,fvmb.name AS brand_name
                    ,fv.model_id
                    ,fvm.name AS model_name
                    ,fv.license_plate
                    ,fv.x_vehicle_service_state AS service_state
                FROM
                    fleet_vehicle fv
                LEFT JOIN res_partner rp ON fv.driver_id = rp.id
                LEFT JOIN res_partner rps ON fv.x_partner_id = rps.id
                LEFT JOIN res_partner ca ON fv.x_center_id = ca.id
                LEFT JOIN fleet_vehicle_model fvm ON fv.model_id = fvm.id
                LEFT JOIN fleet_vehicle_model_brand fvmb ON fvm.brand_id = fvmb.id
                WHERE fv.driver_id = %s;
            """, (user.partner_id.id,))

            vehicles = self.env.cr.dictfetchall()

            # Obtener la url base
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            partner_id = session_info['partner_id']
            # Inyectar los datos en la sesión
            assigned_vehicles = [
                {
                    'id': vehicle['x_vehicle_ref'] or '',
                    'name': vehicle['name'] or '',
                    'supplier_id': vehicle['supplier_id'] or False,
                    'supplier_name': vehicle['supplier_name'] or '',
                    'ca_id': vehicle['ca_id'] or 0,
                    'ca_name': vehicle['ca_name'] or '',
                    'driver_id': vehicle['driver_id'] or False,
                    'driver_name': vehicle['driver_name'] or False,
                    'brand_id': vehicle['brand_id'] or False,
                    'brand_name': vehicle['brand_name'] or '',
                    'model_id': vehicle['model_id'] or False,
                    'model_name': vehicle['model_name'] or '',
                    'license_plate': vehicle['license_plate'] or False,
                    'service_state': vehicle['service_state'] or '',
                    'image_128': "%s/web/image/fleet.vehicle/%s/image_128" % (base_url, vehicle['id']),
                } for vehicle in vehicles
            ]

            # Obtener la zona horaria del usuario actual
            # user_tz = request.env.user.tz or 'UTC'
            # self.env.cr.execute("""
            #     SELECT
            #         ievent.id,
            #         ievent.name,
            #         TO_CHAR(
            #             (ievent.event_date AT TIME ZONE 'UTC') AT TIME ZONE %(user_tz)s,
            #             'YYYY-MM-DD HH24:MI:SS'
            #         ) AS event_date,
            #         ievent.step_number,
            #         ies.ref AS stage_ref,
            #         ievent.user_code,
            #         ievent.event_progress_state AS progress_state,
            #         service.name AS service,
            #         COALESCE(subservice.name->>'es_MX', subservice.name->>'en_US', '') AS sub_service,
            #         ievent.destination_latitude AS latitude,
            #         ievent.destination_longitude AS longitude,
            #         ievent.destination_label AS destination
            #     FROM ike_event ievent
            #     INNER JOIN product_category service ON service.id = ievent.service_id
            #     INNER JOIN product_product pp ON pp.id = ievent.sub_service_id
            #     INNER JOIN product_template subservice ON subservice.id = pp.product_tmpl_id
            #     INNER JOIN ike_event_stage ies ON ies.id = ievent.stage_id
            #     LEFT JOIN ike_event_supplier supplier ON ievent.id = supplier.event_id
            #     LEFT JOIN fleet_vehicle vehicle ON vehicle.id = supplier.truck_id
            #     LEFT JOIN res_partner driver ON driver.id = vehicle.driver_id
            #     WHERE
            #         supplier.selected = true
            #         AND ievent.event_date AT TIME ZONE %(user_tz)s > CURRENT_TIMESTAMP AT TIME ZONE %(user_tz)s
            #         AND ies.ref IN ('assigned', 'searching')
            #         AND driver.id = %(driver_id)s;
            # """, {'user_tz': user_tz, 'driver_id': self.env.user.partner_id.id})
            # assigned_services = self.env.cr.dictfetchall()
            # for service in assigned_services:
            #     service['destination'] = html2plaintext(service['destination'])  # Quitar salto HTML
            session_info.update({
                'x_assigned_vehicles': assigned_vehicles,
                'x_services': [],  # assigned_services,
                'x_image_128': "%s/web/image/fleet.vehicle/%s/image_128" % (base_url, partner_id),
            })

        return session_info
