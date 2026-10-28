# -*- coding: utf-8 -*-

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestMailSendingControl(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env['res.partner'].create({
            'name': 'Mail Guard Test Partner',
            'email': 'mail-guard@example.com',
        })
        cls.template = cls.env['mail.template'].create({
            'name': 'Mail Guard Test Template',
            'model_id': cls.env['ir.model']._get_id('res.partner'),
            'subject': 'Mail guard test',
            'body_html': '<p>Test</p>',
            'email_to': 'mail-guard@example.com',
        })

    def test_company_switch_blocks_and_cancels_email(self):
        self.company.x_allow_email_sending = False
        mail = self.env['mail.mail'].browse(
            self.template.send_mail(self.partner.id)
        )

        self.assertEqual(mail.x_source_mail_template_id, self.template)
        mail.send()

        self.assertEqual(mail.state, 'cancel')
        self.assertIn(self.company.display_name, mail.failure_reason)

    def test_archived_template_is_blocked_even_when_called_directly(self):
        self.company.x_allow_email_sending = True
        self.template.write({
            'active': False,
            'x_allow_email_sending': True,
        })
        mail = self.env['mail.mail'].browse(
            self.template.with_context(active_test=False).send_mail(self.partner.id)
        )

        mail.send()

        self.assertEqual(mail.state, 'cancel')
        self.assertIn('archived', mail.failure_reason)

    def test_enabled_company_and_template_are_allowed(self):
        self.company.x_allow_email_sending = True
        self.template.write({
            'active': True,
            'x_allow_email_sending': True,
        })
        mail = self.env['mail.mail'].browse(
            self.template.send_mail(self.partner.id)
        )

        self.assertFalse(mail._x_email_send_block_reason())
