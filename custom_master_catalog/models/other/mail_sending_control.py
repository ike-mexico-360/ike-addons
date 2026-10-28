# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models, _


_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_allow_email_sending = fields.Boolean(
        string='Allow Email Sending',
        default=False,
        help='Master switch for all outgoing emails of this company.',
    )


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    x_allow_email_sending = fields.Boolean(
        string='Allow Sending',
        default=False,
        help='Allow emails generated from this template when company email sending is enabled.',
    )
    @api.returns('self', lambda value: value.ids)
    def send_mail_batch(self, res_ids, force_send=False, raise_exception=False,
                        email_values=None, email_layout_xmlid=False):
        self.ensure_one()
        return super(
            MailTemplate,
            self.with_context(x_source_mail_template_id=self.id),
        ).send_mail_batch(
            res_ids,
            force_send=force_send,
            raise_exception=raise_exception,
            email_values=email_values,
            email_layout_xmlid=email_layout_xmlid,
        )


class MailComposeMessage(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail(self, auto_commit=False):
        result_mails = self.env['mail.mail'].sudo()
        result_messages = self.env['mail.message']
        for wizard in self:
            source_template_id = wizard.template_id.id if wizard.template_id else False
            result = super(
                MailComposeMessage,
                wizard.with_context(x_source_mail_template_id=source_template_id),
            )._action_send_mail(auto_commit=auto_commit)
            result_mails += result[0]
            result_messages += result[1]
        return result_mails, result_messages


class MailMail(models.Model):
    _inherit = 'mail.mail'

    x_source_mail_template_id = fields.Many2one(
        'mail.template',
        string='Source Email Template',
        readonly=True,
        index=True,
        ondelete='set null',
    )

    @api.model_create_multi
    def create(self, vals_list):
        source_template_id = self.env.context.get('x_source_mail_template_id')
        if source_template_id:
            vals_list = [
                dict(vals, x_source_mail_template_id=vals.get('x_source_mail_template_id') or source_template_id)
                for vals in vals_list
            ]
        return super().create(vals_list)

    def _x_email_company(self):
        self.ensure_one()
        message = self.mail_message_id
        if message.record_company_id:
            return message.record_company_id
        if self.model and self.res_id:
            record = self.env[self.model].sudo().browse(self.res_id).exists()
            if record:
                if record._name == 'res.company':
                    return record
                if 'company_id' in record._fields and record.company_id:
                    return record.company_id
        return self.env.company

    def _x_email_send_block_reason(self):
        self.ensure_one()
        company = self._x_email_company()
        if not company.x_allow_email_sending:
            return _(
                'Email sending is disabled for company %(company)s.',
                company=company.display_name,
            )
        template = self.x_source_mail_template_id
        if template and not template.active:
            return _('The source email template is archived.')
        if template and not template.x_allow_email_sending:
            return _(
                'Email sending is disabled for template %(template)s.',
                template=template.display_name,
            )
        return False

    def _x_cancel_blocked_emails(self):
        for mail in self:
            reason = mail._x_email_send_block_reason()
            if not reason:
                continue
            mail.sudo().write({
                'state': 'cancel',
                'failure_reason': reason,
            })
            notifications = self.env['mail.notification'].sudo().search([
                ('mail_mail_id', '=', mail.id),
                ('notification_status', 'not in', ('sent', 'canceled')),
            ])
            notifications.write({
                'notification_status': 'canceled',
                'failure_reason': reason,
            })
            _logger.info('Outgoing email %s was blocked: %s', mail.id, reason)

    def send(self, auto_commit=False, raise_exception=False, post_send_callback=None):
        blocked = self.filtered(lambda mail: bool(mail._x_email_send_block_reason()))
        allowed = self - blocked
        blocked._x_cancel_blocked_emails()
        if allowed:
            return super(MailMail, allowed).send(
                auto_commit=auto_commit,
                raise_exception=raise_exception,
                post_send_callback=post_send_callback,
            )
        return True
