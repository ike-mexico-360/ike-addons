# -*- coding: utf-8 -*-

from odoo.fields import Command
from odoo.tests import Form, SingleTransactionCase, TransactionCase, tagged
from odoo.exceptions import AccessError, UserError, ValidationError


@tagged('standard')
class TestIkeEvent(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestIkeEvent, cls).setUpClass()

        cls.empty_ike_event = cls.env['ike.event'].create({})

    def test_ike_event_vial_truck_algorithm(self):
        """ Check if all works fine """

        event_id = self.empty_ike_event

        # ? User and Membership
        nu_user_id = self.env['custom.nus'].search([('disabled', '=', False)], limit=1)
        membership_id = self.env['custom.membership.nus'].search([
            ('nus_id', '=', nu_user_id.id),
            ('disabled', '=', False)
        ], limit=1)
        event_id.write({
            'user_id': nu_user_id.id,
            'user_membership_id': membership_id.id,
        })
        # ? Forward 1.1: Set User Data
        event_id.action_forward()
        event_id.write({
            'service_id': self.env.ref('custom_master_catalog.ike_product_category_vial').id,
            'sub_service_id': self.env.ref('custom_master_catalog.ike_product_product_vial_truck').id,
        })

        # ? Forward 2.1: Set Service Data
        event_id.action_forward()
        # res_id = self.env[event_id.service_res_model].search([('event_id', '=', event_id.id)], limit=1, order='id desc')
        sub_res_id = self.env[event_id.sub_service_res_model].search([('event_id', '=', event_id.id)], limit=1, order='id desc')

        # ? Forward 2.2: Set User Service Data
        event_id.action_forward()

        # ? Forward 2.3: Set Location Data
        event_id.location_latitude = '21.16991205'
        event_id.location_longitude = '-86.84517643'
        event_id.location_zip_code = '77516'
        event_id.action_forward()

        # ? Forward 2.4: Set Survey Data / Set Product Data
        event_id.action_forward()

        # ? Forward 2.5: Set Destination Data
        event_id.action_forward()

        # ? Forward 2.6: Set Product Data
        platform_truck_type_id = self.env['custom.vehicle.type'].search([('name', '=', 'Plataforma')], limit=1)
        sub_res_id.truck_type_id = platform_truck_type_id.id  # type: ignore
        event_id.action_forward()

        # ? Forward 3.1: Set Supplier Data
        event_id.action_forward()

        event_id.action_search_electronic_suppliers()

        print(event_id)
