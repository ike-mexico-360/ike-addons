# -*- coding: utf-8 -*-

import logging

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError, ValidationError

from ..other_models.ike_event_batcher import event_batcher

_logger = logging.getLogger(__name__)


class IkeEventSupplier_Person(models.Model):
    _inherit = 'ike.event.supplier'

    person_domain = fields.Binary(compute='_compute_person_domain')

    # === ONCHANGE === #
    @api.onchange('person_id')
    def _onchange_person_id(self):
        if self.person_id:
            self.assigned = self.person_id.name
            self.name = f"{_('Reference')}: {self.person_ref}"

    # === COMPUTE === #
    @api.depends('supplier_id')
    def _compute_person_domain(self):
        for rec in self:
            domain = [
                ('disabled', '=', False),
            ]

            rec.person_domain = domain
