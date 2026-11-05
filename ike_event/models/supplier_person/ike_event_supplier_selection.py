# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, Command, _
from odoo.exceptions import UserError, ValidationError

from ..other_models.ike_event_batcher import event_batcher

_logger = logging.getLogger(__name__)


class IkeEventSupplier_SelectionPerson(models.Model):
    _inherit = 'ike.event.supplier'

    # === HOOKS === #
    def _action_assign_person(self):
        pass

    def action_change_service_person(self, person_id: int):
        self.broadcastReload(reload_type='person_changed')

    def _change_previous_person_state(self, old_person):
        pass
