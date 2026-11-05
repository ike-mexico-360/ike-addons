# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, Command, _
from odoo.exceptions import UserError, ValidationError

from ..other_models.ike_event_batcher import event_batcher

_logger = logging.getLogger(__name__)


class IkeEvent_SearchPerson(models.Model):
    _inherit = 'ike.event'

    def _get_service_suppliers_person_data(self) -> tuple[list[dict], dict]:
        """ Implementation """
        return [], {}
