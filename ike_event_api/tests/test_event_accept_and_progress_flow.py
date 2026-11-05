# -*- coding: utf-8 -*-

import json

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestEventAcceptAndProgressFlow(HttpCase):
    """End-to-end regression test mirroring how the two halves of this flow
    are actually driven in production:

    - Everything up to and including reaching the 'searching' stage (the
      point where a supplier search would be launched) goes through the
      same generic web-client endpoints the browser uses when an operator
      fills the event form and clicks "Continuar"
      (/web/dataset/call_kw and /web/dataset/call_button - see
      ike_event/static/src/views/ike_event_form.js::_executeAction, which
      calls exactly call_button with {model, method, args, kwargs:{context}}).
    - Supplier acceptance and every progress update from there on (on_route,
      arrived, contacted, ..., finalized) go through the real mobile/supplier
      HTTP API: /ike/event/accept and /ike/catalog/events/set/progress_state
      (ike_event_api/controllers/events.py and catalogs.py).

    This is the regression net for the mobile-app bug fixed in
    catalogs.check_progress_state_transition: a supplier reporting progress
    out of order used to leave the parent event stuck in 'assigned' or
    'in_progress' forever, silently. Driving the whole post-acceptance
    sequence through the real route end to end (not direct ORM calls) proves
    the fix holds for actual HTTP callers, not just the extracted function.

    Creating the notified supplier line itself (the bridge between "search
    launched" and "supplier accepts") is done directly via the ORM: there is
    no public endpoint that performs the full geographical-search algorithm
    without real custom.geographical.area/postal-code data, so this uses the
    same from-scratch, minimal-fixture approach validated in
    ike_event/tests/test_event_full_lifecycle.py, standing in for "the search
    found and notified this supplier".
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.category_vial = cls.env.ref('custom_master_catalog.ike_product_category_vial')
        cls.sub_service = cls.env['product.product'].search([
            ('categ_id', '=', cls.category_vial.id),
            ('default_code', '=', 'tire_change'),
        ], limit=1)

        cls.vehicle_type = cls.env['custom.vehicle.type'].create({
            'name': 'Plataforma Test API',
            'x_service_id': cls.category_vial.id,
            'x_subservice_ids': [Command.link(cls.sub_service.id)],
        })

        account = cls.env['res.partner'].create({
            'name': 'Cuenta Demo Test API',
            'is_company': True,
            'company_type': 'company',
            'x_is_account': True,
        })
        plan = cls.env['custom.membership.plan'].create({
            'name': 'Plan Demo Test API',
            'account_id': account.id,
            'product_line_ids': [Command.create({
                'service_id': cls.category_vial.id,
                'sub_service_ids': [Command.link(cls.sub_service.id)],
                'period_per_event': 5,
                'period': 'monthly',
                'unlimited_amount': True,
            })],
        })
        cls.nu_user = cls.env['custom.nus'].create({'name': 'Usuario Prueba Test API'})
        cls.membership = cls.env['custom.membership.nus'].create({
            'nus_id': cls.nu_user.id,
            'membership_plan_id': plan.id,
            'subscription_validity': True,
        })

        cls.supplier_partner = cls.env['res.partner'].create({
            'name': 'Proveedor Demo Test API',
            'is_company': True,
            'company_type': 'company',
            'country_id': cls.env.ref('base.mx').id,
            'x_is_supplier': True,
            'x_is_electronic': True,
            'vat': 'XAXX010101000',
        })
        center = cls.supplier_partner.x_supplier_center_ids[:1]
        model = cls.env['fleet.vehicle.model'].create({
            'name': 'Modelo Demo Test API', 'brand_id': cls.env.ref('fleet.brand_audi').id,
        })
        driver = cls.env['res.partner'].create({'name': 'Chofer Demo Test API'})
        cls.vehicle = cls.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': 'TESTAPI-01',
            'x_economic_number': 'ECO-TESTAPI-01',
            'x_partner_id': cls.supplier_partner.id,
            'x_center_id': center.id if center else False,
            'x_vehicle_type': cls.vehicle_type.id,
            'driver_id': driver.id,
            'x_vehicle_service_state': 'available',
        })

    # === RPC helpers that mirror exactly what the web client sends === #
    def _rpc(self, url, params):
        response = self.url_open(
            url,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}).encode(),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200, f"{url} -> HTTP {response.status_code}: {response.text}")
        body = response.json()
        self.assertNotIn(
            'error', body,
            f"{url} devolvio un error JSON-RPC: {json.dumps(body.get('error'), indent=2)}",
        )
        return body['result']

    def _call_kw(self, model, method, args, kwargs=None):
        return self._rpc('/web/dataset/call_kw', {
            'model': model, 'method': method, 'args': args, 'kwargs': kwargs or {},
        })

    def _call_button(self, model, method, args, kwargs=None):
        return self._rpc('/web/dataset/call_button', {
            'model': model, 'method': method, 'args': args, 'kwargs': kwargs or {},
        })

    def _event_stage(self, event_id):
        data = self._call_kw('ike.event', 'read', [[event_id], ['stage_id', 'step_number']])[0]
        stage = self.env['ike.event.stage'].browse(data['stage_id'][0])
        return (stage.ref, data['step_number'])

    def test_web_build_then_api_accept_and_progress(self):
        self.authenticate('admin', 'admin')

        # === FASE 1: "interfaz web" (operador llenando el formulario) === #
        event_id = self._call_kw('ike.event', 'create', [[{}]])[0]
        self.assertEqual(self._event_stage(event_id), ('draft', 1))

        self._call_kw('ike.event', 'write', [[event_id], {
            'user_id': self.nu_user.id, 'user_membership_id': self.membership.id,
        }])
        self._call_button('ike.event', 'action_forward', [[event_id]], {})
        self.assertEqual(self._event_stage(event_id), ('capturing', 1))

        self._call_kw('ike.event', 'write', [[event_id], {
            'service_id': self.category_vial.id, 'sub_service_id': self.sub_service.id,
        }])
        self._call_button('ike.event', 'action_forward', [[event_id]], {})
        self.assertEqual(self._event_stage(event_id), ('capturing', 2))

        self._call_button('ike.event', 'action_forward', [[event_id]], {})
        self.assertEqual(self._event_stage(event_id), ('capturing', 3))

        self._call_kw('ike.event', 'write', [[event_id], {
            'location_latitude': '19.432608',
            'location_longitude': '-99.133209',
            'location_zip_code': '06000',
        }])
        self._call_button('ike.event', 'action_forward', [[event_id]], {})
        self.assertEqual(self._event_stage(event_id), ('capturing', 4))

        # capturing/4 -> capturing/6: step 5 (destino) solo aplica a town_truck.
        self._call_button('ike.event', 'action_forward', [[event_id]], {})
        self.assertEqual(self._event_stage(event_id), ('capturing', 6))

        # Prerequisitos de capturing/6 (action_set_user_sub_service_data),
        # llenados tal como lo haria el formulario web: tipo de vehiculo en
        # el sub-registro, y al menos un producto no-display.
        event = self.env['ike.event'].browse(event_id)
        sub_res_id = self.env[event.sub_service_res_model].search(
            [('event_id', '=', event_id)], limit=1, order='id desc')
        self._call_kw(event.sub_service_res_model, 'write', [[sub_res_id.id], {
            'service_vehicle_type_ids': [Command.link(self.vehicle_type.id)],
        }])
        a_product = self.env['product.product'].search([('sale_ok', '=', True)], limit=1)
        self._call_kw('ike.event.product', 'create', [[{
            'event_id': event_id, 'product_id': a_product.id, 'supplier_number': event.supplier_number,
        }]])

        self._call_button('ike.event', 'action_forward', [[event_id]], {})
        self.assertEqual(
            self._event_stage(event_id), ('searching', 1),
            "El evento debe quedar en 'searching' justo antes de lanzar la busqueda de proveedor",
        )

        # === Puente (no es ni web ni API): simular que la busqueda ya === #
        # === encontro y notifico a este proveedor.                   === #
        supplier_line = self.env['ike.event.supplier'].create({
            'event_id': event_id,
            'supplier_id': self.supplier_partner.id,
            'truck_id': self.vehicle.id,
            'state': 'notified',
            'is_manual': False,
            'assignation_type': 'electronic',
        })

        # === FASE 2: API real (app movil del proveedor) === #
        accept_result = self._rpc('/ike/event/accept', {
            'event_id': event_id,
            'vehicle_id': self.vehicle.x_vehicle_ref,
        })
        self.assertEqual(accept_result.get('status'), 'success', accept_result)
        self.assertEqual(
            self._event_stage(event_id), ('assigned', 1),
            "El evento debe avanzar a assigned/1 tras /ike/event/accept",
        )
        supplier_line.invalidate_recordset()
        self.assertEqual(
            supplier_line.state, 'assigned',
            "assignation_type='electronic' debe auto-confirmar (action_assign) en el accept",
        )

        def _report_progress(progress_state):
            result = self._rpc('/ike/catalog/events/set/progress_state', {
                'event_id': event_id,
                'vehicle_id': self.vehicle.x_vehicle_ref,
                'progress_state': progress_state,
            })
            self.assertEqual(result.get('status'), 'success', result)

        # progress_state=1 (on_route) es el unico salto obligatorio: es lo
        # unico que mueve al evento fuera de 'assigned' (ver
        # check_progress_state_transition / action_on_route). Se verifica
        # aparte, antes de seguir avanzando.
        _report_progress(1)
        self.assertEqual(
            self._event_stage(event_id), ('in_progress', 1),
            "El evento debe estar en in_progress/1 apenas se reporto on_route (progress_state=1)",
        )

        for progress_state in (2, 3, 4, 5, 6):
            _report_progress(progress_state)

        supplier_line.invalidate_recordset()
        self.assertEqual(supplier_line.stage_ref, 'finalized')

        event.invalidate_recordset()
        self.assertIn(
            event.stage_id.ref, ('completed', 'verifying', 'closed'),
            f"El evento quedo atorado en '{event.stage_id.ref}' tras progress_state=6 (finalizado)",
        )
