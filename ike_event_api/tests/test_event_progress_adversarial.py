# -*- coding: utf-8 -*-

import json

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged('-at_install', 'post_install')
class TestEventProgressAdversarial(HttpCase):
    """Adversarial / negative-path coverage for the two mobile-API endpoints
    touched by today's fixes: /ike/event/accept and
    /ike/catalog/events/set/progress_state.

    Empirically confirmed first (see memory): a werkzeug BadRequest/NotFound
    raised inside a type='json' route surfaces as HTTP 200 with a JSON-RPC
    `error` envelope, not a real 4xx status code - so every assertion here
    checks the JSON-RPC body, never response.status_code, for the
    error/success distinction.

    These fixtures are built directly via the ORM (writing stage_id/state),
    not by walking the full action_forward chain - the full lifecycle is
    already covered by test_event_accept_and_progress_flow.py; this file is
    only about how the endpoints behave under bad/adversarial input.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.supplier_partner = cls.env['res.partner'].create({
            'name': 'Proveedor Adversarial',
            'is_company': True, 'company_type': 'company',
            'country_id': cls.env.ref('base.mx').id,
            'x_is_supplier': True,
            'vat': 'XAXX010101000',
        })

    def _make_vehicle(self, ref_suffix):
        model = self.env['fleet.vehicle.model'].create({
            'name': f'Modelo Adversarial {ref_suffix}', 'brand_id': self.env.ref('fleet.brand_audi').id,
        })
        driver = self.env['res.partner'].create({'name': f'Chofer Adversarial {ref_suffix}'})
        return self.env['fleet.vehicle'].create({
            'model_id': model.id,
            'license_plate': f'ADV-{ref_suffix}',
            'x_economic_number': f'ECO-ADV-{ref_suffix}',
            'x_partner_id': self.supplier_partner.id,
            'x_vehicle_type': self.env['custom.vehicle.type'].create({'name': f'Tipo {ref_suffix}'}).id,
            'driver_id': driver.id,
            'x_vehicle_service_state': 'available',
        })

    def _make_event_at_assigned(self, vehicle, state='assigned', stage_xmlid='ike_event.ike_service_stage_assigned'):
        event = self.env['ike.event'].create({})
        event.write({
            'stage_id': self.env.ref('ike_event.ike_event_stage_assigned').id,
            'step_number': 1,
        })
        supplier_line = self.env['ike.event.supplier'].create({
            'event_id': event.id,
            'supplier_id': self.supplier_partner.id,
            'truck_id': vehicle.id,
            'state': state,
            'assignation_type': 'electronic',
            'stage_id': self.env.ref(stage_xmlid).id,
        })
        return event, supplier_line

    def _rpc(self, url, params):
        response = self.url_open(
            url,
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call', 'params': params}).encode(),
            headers={'Content-Type': 'application/json'},
        )
        self.assertEqual(response.status_code, 200, f"{url} -> HTTP {response.status_code}: {response.text}")
        return response.json()

    def _assert_jsonrpc_error(self, body, expected_substring=None):
        self.assertIn('error', body, f"Se esperaba un error JSON-RPC, se obtuvo: {body}")
        if expected_substring:
            message = body['error'].get('data', {}).get('message', '') + body['error'].get('message', '')
            self.assertIn(expected_substring, message, body['error'])

    def setUp(self):
        super().setUp()
        self.authenticate('admin', 'admin')

    # === /ike/catalog/events/set/progress_state: parametros invalidos === #
    def test_progress_state_missing_event_id(self):
        vehicle = self._make_vehicle('M1')
        body = self._rpc('/ike/catalog/events/set/progress_state', {
            'vehicle_id': vehicle.x_vehicle_ref, 'progress_state': 1,
        })
        self._assert_jsonrpc_error(body, 'Missing parameters')

    def test_progress_state_missing_vehicle_id(self):
        event, _ = self._make_event_at_assigned(self._make_vehicle('M2'))
        body = self._rpc('/ike/catalog/events/set/progress_state', {
            'event_id': event.id, 'progress_state': 1,
        })
        self._assert_jsonrpc_error(body, 'Missing parameters')

    def test_progress_state_non_numeric(self):
        vehicle = self._make_vehicle('M3')
        event, _ = self._make_event_at_assigned(vehicle)
        body = self._rpc('/ike/catalog/events/set/progress_state', {
            'event_id': event.id, 'vehicle_id': vehicle.x_vehicle_ref, 'progress_state': 'abc',
        })
        self._assert_jsonrpc_error(body, 'Invalid progress_state')

    def test_progress_state_out_of_range(self):
        vehicle = self._make_vehicle('M4')
        event, _ = self._make_event_at_assigned(vehicle)
        for bad_value in (99, -1, 7):
            body = self._rpc('/ike/catalog/events/set/progress_state', {
                'event_id': event.id, 'vehicle_id': vehicle.x_vehicle_ref, 'progress_state': bad_value,
            })
            self._assert_jsonrpc_error(body, 'Invalid progress_state value')

    # === Evento/vehiculo inexistentes: debe degradar con gracia, no 500 === #
    def test_progress_state_nonexistent_event_or_vehicle(self):
        body = self._rpc('/ike/catalog/events/set/progress_state', {
            'event_id': 999999999, 'vehicle_id': 'NO-EXISTE', 'progress_state': 1,
        })
        self.assertNotIn('error', body, f"No deberia reventar con un 500, deberia degradar con gracia: {body}")
        self.assertEqual(body['result'].get('status'), 'error')

    # === Salto de progreso bloqueado via HTTP real (no solo la funcion pura) === #
    def test_progress_state_skip_blocked_over_http_and_state_unchanged(self):
        vehicle = self._make_vehicle('M5')
        event, supplier_line = self._make_event_at_assigned(vehicle)  # stage_ref supplier = 'assigned' (progress 0)

        body = self._rpc('/ike/catalog/events/set/progress_state', {
            'event_id': event.id, 'vehicle_id': vehicle.x_vehicle_ref, 'progress_state': 3,
        })
        self._assert_jsonrpc_error(body, 'on_route')

        # Nada debio cambiar: ni el supplier ni el evento avanzaron.
        supplier_line.invalidate_recordset()
        event.invalidate_recordset()
        self.assertEqual(supplier_line.stage_ref, 'assigned')
        self.assertEqual(event.stage_ref, 'assigned')

    # === No se puede retroceder una vez finalizado === #
    def test_progress_state_cannot_regress_after_finalized(self):
        vehicle = self._make_vehicle('M6')
        event, supplier_line = self._make_event_at_assigned(
            vehicle, stage_xmlid='ike_event.ike_service_stage_finalized')

        body = self._rpc('/ike/catalog/events/set/progress_state', {
            'event_id': event.id, 'vehicle_id': vehicle.x_vehicle_ref, 'progress_state': 3,
        })
        self._assert_jsonrpc_error(body, 'lower')
        supplier_line.invalidate_recordset()
        self.assertEqual(supplier_line.stage_ref, 'finalized')

    # === Fix de hoy: dos lineas 'assigned' para el mismo vehiculo/evento === #
    def test_progress_state_resolves_most_recent_line_when_duplicated(self):
        """Reproduce a proposito el escenario que motivo el ORDER BY ies.id
        DESC: dos lineas ike.event.supplier en estado 'assigned' para el
        mismo evento y vehiculo (ej. una reasignacion que no debio dejar dos
        lineas activas). El endpoint debe resolver de forma deterministica
        a la mas reciente, no a una aleatoria."""
        vehicle = self._make_vehicle('M7')
        event, old_line = self._make_event_at_assigned(vehicle)
        new_line = self.env['ike.event.supplier'].create({
            'event_id': event.id,
            'supplier_id': self.supplier_partner.id,
            'truck_id': vehicle.id,
            'state': 'assigned',
            'assignation_type': 'electronic',
            'stage_id': self.env.ref('ike_event.ike_service_stage_assigned').id,
        })
        self.assertGreater(new_line.id, old_line.id)

        body = self._rpc('/ike/catalog/events/set/progress_state', {
            'event_id': event.id, 'vehicle_id': vehicle.x_vehicle_ref, 'progress_state': 1,
        })
        self.assertNotIn('error', body, body)

        old_line.invalidate_recordset()
        new_line.invalidate_recordset()
        self.assertEqual(
            new_line.stage_ref, 'on_route',
            "Debio avanzar la linea MAS RECIENTE (mayor id), consistente con el ORDER BY del fix",
        )
        self.assertEqual(
            old_line.stage_ref, 'assigned',
            "La linea vieja no debio tocarse",
        )

    # === /ike/event/accept: doble aceptacion === #
    def test_accept_twice_second_call_fails(self):
        vehicle = self._make_vehicle('M8')
        event = self.env['ike.event'].create({})
        event.write({
            'stage_id': self.env.ref('ike_event.ike_event_stage_searching').id,
            'step_number': 1,
            # action_accept() -> action_assign() (electronic) calcula ruta y
            # exige ubicacion del evento, aunque el sub-servicio no la use.
            'location_latitude': '19.432608',
            'location_longitude': '-99.133209',
        })
        supplier_line = self.env['ike.event.supplier'].create({
            'event_id': event.id,
            'supplier_id': self.supplier_partner.id,
            'truck_id': vehicle.id,
            'state': 'notified',
            'assignation_type': 'electronic',
        })

        first = self._rpc('/ike/event/accept', {'event_id': event.id, 'vehicle_id': vehicle.x_vehicle_ref})
        self.assertNotIn('error', first, first)
        self.assertEqual(first['result'].get('status'), 'success')

        second = self._rpc('/ike/event/accept', {'event_id': event.id, 'vehicle_id': vehicle.x_vehicle_ref})
        self.assertIn(
            'error', second,
            f"Una segunda aceptacion del mismo evento/vehiculo no deberia volver a tener exito: {second}",
        )
