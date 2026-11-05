# -*- coding: utf-8 -*-

from werkzeug.exceptions import BadRequest

from odoo.tests import TransactionCase, tagged

from odoo.addons.ike_event_api.controllers.catalogs import check_progress_state_transition


@tagged('standard')
class TestCatalogsProgressStateTransition(TransactionCase):
    """Regression/adversarial coverage for the fix in
    /ike/catalog/events/set/progress_state (ike_event_api/controllers/catalogs.py).

    Bug: the mobile app endpoint only blocked going backward, so a retry/race/
    offline-sync could jump straight from 'assigned' (0) to any later state
    (e.g. 'finalized'/6) without ever passing through 'on_route' (1) -
    which is the ONLY place that moves the parent ike.event from 'assigned'
    to 'in_progress' (see ike_event_supplier_stages.action_on_route). The
    event would then stay stuck in 'assigned' forever, silently.

    Fix: the 0 -> 1 hop is now the only mandatory sequential step. From 1
    onward, forward jumps are legitimate (not every service has a vehicle
    en route to a second destination) and remain unrestricted.
    """

    def _assert_allowed(self, current_state, new_state):
        try:
            check_progress_state_transition(current_state, new_state)
        except BadRequest as exc:
            self.fail(
                f"Se esperaba permitir current_state={current_state} -> "
                f"new_state={new_state}, pero se bloqueó: {exc}"
            )

    def _assert_blocked(self, current_state, new_state):
        with self.assertRaises(BadRequest):
            check_progress_state_transition(current_state, new_state)

    # === The one mandatory hop: 0 -> 1 === #
    def test_cannot_skip_on_route_from_assigned(self):
        """0 -> 2..6 directo debe bloquearse: on_route (1) nunca puede saltarse."""
        for target in (2, 3, 4, 5, 6):
            self._assert_blocked(current_state=0, new_state=target)

    def test_cannot_skip_on_route_from_unstarted(self):
        """Estado no mapeado (-1, nunca inició el flujo) tampoco puede saltar a 1+."""
        for target in (1, 2, 3, 4, 5, 6):
            self._assert_blocked(current_state=-1, new_state=target)

    def test_assigned_to_on_route_is_allowed(self):
        self._assert_allowed(current_state=0, new_state=1)

    def test_unstarted_to_assigned_is_allowed(self):
        self._assert_allowed(current_state=-1, new_state=0)

    # === From on_route (1) onward, forward jumps are legitimate === #
    def test_jumps_allowed_once_on_route_reached(self):
        """Tras pasar por on_route (1), saltarse 2-5 es un escenario de negocio
        valido (sin vehiculo / sin segundo destino), no debe bloquearse."""
        for current, target in [(1, 2), (1, 3), (1, 6), (2, 6), (3, 6), (1, 4), (2, 4)]:
            self._assert_allowed(current_state=current, new_state=target)

    # === Idempotent retries (mobile network retries resending the same state) === #
    def test_resending_same_state_is_allowed(self):
        for state in (-1, 0, 1, 2, 3, 4, 5, 6):
            self._assert_allowed(current_state=state, new_state=state)

    # === Never allow going backward, at any point in the flow === #
    def test_cannot_go_backward(self):
        for current, target in [(1, 0), (3, 1), (6, 5), (6, 0), (2, 1)]:
            self._assert_blocked(current_state=current, new_state=target)

    # === Terminal state === #
    def test_finalized_cannot_move_anywhere_else(self):
        self._assert_allowed(current_state=6, new_state=6)
        for target in (0, 1, 2, 3, 4, 5):
            self._assert_blocked(current_state=6, new_state=target)
