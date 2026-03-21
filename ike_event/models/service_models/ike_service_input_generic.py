# -*- coding: utf-8 -*-

import base64
import os

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IkeServiceGeneric(models.Model):
    _name = 'ike.service.input.generic'
    _inherit = ['ike.service.input.model', 'mail.thread', 'mail.tracking.duration.mixin']
    _description = 'Service Input Generic'
    _track_duration_field = 'stage_id'

    # === FLOW ACTIONS === #
    def set_event_summary_user_service_data(self):
        pass

    def set_event_summary_user_location_data(self):
        pass

    def set_event_summary_survey_data(self):
        pass

    def set_event_summary_destination_data(self):
        pass

    def set_event_summary_user_subservice_data(self):
        pass

    def set_event_summary_supplier_data(self):
        pass


class IkeServiceInputGeneric(models.Model):
    _name = 'ike.service.input.generic.sub'
    _inherit = ['ike.service.input']
    _description = 'Service Input Generic Subservice'
