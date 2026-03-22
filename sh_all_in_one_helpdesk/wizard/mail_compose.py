# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

import re
from odoo import api, fields, models, tools, _
# import html2text
from odoo.exceptions import UserError


class MailMessage(models.Model):
    _inherit = 'mail.message'

    @api.model_create_multi
    def create(self, vals_list):

        for vals in vals_list:
            if vals.get('model') and vals.get('model') == 'sh.helpdesk.ticket':
                ticket_id = self.env['sh.helpdesk.ticket'].browse(
                    vals.get('res_id'))
                if ticket_id:
                    if vals.get('author_id') and vals.get(
                            'author_id') == ticket_id.partner_id.id:
                        if ticket_id.sh_auto_followup:
                            ticket_id.sh_auto_followup = False
                        ticket_id.state = 'customer_replied'
                        ticket_id.replied_date = ticket_id.write_date
                    elif vals.get('author_id') and vals.get(
                            'author_id') != 2 and vals.get(
                                'author_id'
                    ) != ticket_id.partner_id.id and vals.get('parent_id'):
                        ticket_id.state = 'staff_replied'
                        ticket_id.replied_date = ticket_id.write_date
        return super(MailMessage, self).create(vals_list)

    # def portal_message_format(self):
    #     return self._portal_message_format([
    #         'id', 'body', 'date', 'author_id', 'email_from',  # base message fields
    #         'message_type', 'subtype_id', 'is_internal', 'subject',  # message specific
    #         'model', 'res_id', 'record_name',  # document related
    #     ])

    # -----------------------------------------------------------------
    # CUSTOM CODE "_portal_message_format" FOR ODOO COMMUNITY ISSUE
    # -----------------------------------------------------------------

    # def _portal_message_format(self, fields_list):
    #     vals_list = self._message_format(fields_list)
    #     message_subtype_note_id = self.env['ir.model.data']._xmlid_to_res_id(
    #         'mail.mt_note')
    #     IrAttachmentSudo = self.env['ir.attachment']
    #     if vals_list == []:
    #         for vals in vals_list:
    #             vals['is_message_subtype_note'] = message_subtype_note_id and vals.get(
    #                 'subtype_id', [False])[0] == message_subtype_note_id
    #             for attachment in vals.get('attachment_ids', []):
    #                 if not attachment.get('access_token'):
    #                     attachment['access_token'] = IrAttachmentSudo.browse(
    #                         attachment['id']).generate_access_token()[0]
    #     return vals_list

    # -----------------------------------------------------------------
    # CUSTOM CODE "_portal_message_format" FOR ODOO COMMUNITY ISSUE
    # -----------------------------------------------------------------


class MailComposeWizard(models.TransientModel):
    _inherit = 'mail.compose.message'

    body_str = fields.Html('Body')
    is_wp = fields.Boolean('Whatsapp ?')

    def action_send_wp(self):
        # text = html2text.html2text(self.body)
        # helpdesk_ticket = self.env['sh.helpdesk.ticket'].browse(self.res_id)

        # self.update({
        #     'partner_ids':([4,helpdesk_ticket.partner_id.id])
        # })

        text = tools.html2plaintext(self.body)
        if not self.partner_ids[0].mobile:
            raise UserError('Partner Mobile Number Not Exist !')
        phone = str(self.partner_ids[0].mobile)
        # base_url = self.env['ir.config_parameter'].get_param(
        #     'web.base.url')
        base_url = self.get_base_url()
        if self.attachment_ids:
            text += '%0A%0A Other Attachments :'
            for attachment in self.attachment_ids:
                attachment.generate_access_token()
                text += '%0A%0A'
                text += base_url+'/web/content/ir.attachment/' + \
                    str(attachment.id)+'/datas?access_token=' + \
                    attachment.access_token
        context = dict(self._context or {})
        active_id = context.get('active_id', False)
        active_model = context.get('active_model', False)

        if text and active_id and active_model:
            message = str(text).replace('*', '').replace('_', '').replace(
                '%0A', '<br/>').replace('%20', ' ').replace('%26', '&')
            if active_model == 'sh.helpdesk.ticket' and self.env[
                    'sh.helpdesk.ticket'].browse(
                        active_id).company_id.sh_display_in_chatter:
                self.env['mail.message'].create({
                    'partner_ids': [(6, 0, self.partner_ids.ids)],
                    'model':
                    'sh.helpdesk.ticket',
                    'res_id':
                    active_id,
                    'author_id':
                    self.env.user.partner_id.id,
                    'body':
                    message or False,
                    'message_type':
                    'comment',
                })
        url = "https://web.whatsapp.com/send?l=&phone=" + phone + "&text=" + text
        return {
            'type': 'ir.actions.act_url',
            'url': url,
            'target': 'new',
        }
