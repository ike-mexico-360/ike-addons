# -*- coding: utf-8 -*-

from odoo.tests import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestIkeEventCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super(TestIkeEventCommon, cls).setUpClass()

        # Common
        cls.empty_ike_event = cls.env['ike.event'].create({})
