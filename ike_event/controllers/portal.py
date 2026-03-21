# -*- coding: utf-8 -*-

import json
import logging
import requests
import time

from odoo.http import request, route, Controller

_logger = logging.getLogger(__name__)


class PortalTestController(Controller):
    @route(
        ['/my/ike_event_suppliers'],
        type='http',
        auth="user",
        website=True,
        sitemap=False,
    )
    def portal_my_custom_roots_table(self, **kwargs):
        values = {
            'word': 'OWL',
        }
        return request.render("ike_event.portal_my_ike_event_suppliers", values)
