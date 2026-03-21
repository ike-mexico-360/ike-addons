# -*- coding: utf-8 -*-

from odoo.fields import Command

from odoo.tests import Form, SingleTransactionCase, TransactionCase, tagged
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.base.tests.common import BaseCommon


class CustomMasterCatalogCommon(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # CATALOGS
        cls.credit_account_identification_id = cls.env.ref(
            'custom_master_catalog.account_identification_credit')
        cls.bank_account_type_id = cls.env.ref(
            'custom_master_catalog.account_type_bank')
        cls.employee_id = cls.env['hr.employee'].create({
            'name': 'Richard',
            'gender': 'male',
            'country_id': cls.env.ref('base.be').id,
        })
        # RES PARTNERS
        cls.empty_partner_id = cls.env['res.partner'].create({
            'name': 'Test Empty Partner'
        })
        cls.ike_partner_id = cls.env['res.partner'].create({
            'name': 'Test Ike 01',
            'is_company': True,
            'company_type': 'company',
            'x_is_ike': True,
        })
        cls.client_partner_id = cls.env['res.partner'].create({
            'is_company': True,
            'company_type': 'company',
            'x_is_client': True,
            'name': 'Test Client 01',
        })
        cls.account_bank_partner_id = cls.env['res.partner'].create({
            'is_company': True,
            'company_type': 'company',
            'x_is_account': True,
            'name': 'Test Account 01',
            'parent_id': cls.empty_partner_id.id,
            'ref': 'ACCOUNT0001',
            'x_account_type_id': cls.bank_account_type_id.id,
            'x_account_identification_id': cls.credit_account_identification_id.id,
            'x_account_responsible_id': cls.employee_id.id,
            'x_account_vnd_did': '9999999999',
            'x_invoice_company_id': cls.ike_partner_id.id,
        })

    def test_res_partner_account_form(self):
        """ Check if Partner Account Form is working as expected.
        """
        form_view_id = self.env.ref('custom_master_catalog.res_partner_account_view_search')

        partner_model = self.env['res.partner'].with_context(
            default_company_type='company',
            default_is_company=True,
            default_x_is_account=True,
            x_account_view=True
        )

        with self.assertRaises(ValueError):
            with Form(partner_model, form_view_id) as partner_form:
                partner_form.name = "Test Account 01"

        # with cs_form.line_ids.new() as line:
        #     line.product_id = self.product1
        #     line.qty = 4.0
        # with cs_form.line_ids.new() as line:
        #     line.product_id = self.product2
        #     line.qty = 5.0
        # cs_form.save()

        # # Verify Details
        # self.assertRecordValues(
        #     cs.line_ids,
        #     [
        #         {'description': self.product1.name, 'subtotal': 80.00},
        #         {'description': self.product2.name, 'subtotal': 75.00},
        #     ],
        # )

    @classmethod
    def _create_account(cls, **create_vals):
        return cls.env['res.partner'].create({
            'name': "Test Account",
            'is_company': True,
            'company_type': 'company',
            'x_is_account': True,
            **create_vals,
        })
