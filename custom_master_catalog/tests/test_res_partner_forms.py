# -*- coding: utf-8 -*-

from odoo.fields import Command

from odoo.tests import Form, SingleTransactionCase, TransactionCase, tagged
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.custom_master_catalog.tests.res_partner_common import ResPartnerCommon


class TestResPartnerForms(ResPartnerCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_res_partner_account_form(self):
        """ Check if Partner Account Form is working as expected.
        """
        form_view_id = self.env.ref('custom_master_catalog.res_partner_account_view_form')

        partner_model = self.env['res.partner'].with_context(
            default_company_type='company',
            default_is_company=True,
            default_x_is_account=True,
            x_account_view=True
        )

        # Test WITHOUT all required form fields
        with self.assertRaises(AssertionError):
            with Form(partner_model, form_view_id) as f:
                f.name = "Test Account 01"

                f.save()

        # Test WITH all required form fields
        with Form(partner_model, form_view_id) as f:
            f.name = "Test Account 01"
            f.x_business_name = "Test Account SA de CV"
            f.parent_id = self.client_partner_id
            f.ref = "TEST0001"
            f.x_account_type_id = self.bank_account_type_id
            f.x_account_identification_id = self.credit_account_identification_id
            f.x_use_parent_invoice_info = True
            f.x_account_vnd_did = '9999999999'
            f.x_account_responsible_id = self.employee_id
            f.x_invoice_company_id = self.ike_partner_id
            f.x_partner_contact = 'Partner Contact'

            f.save()
