
# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import _, api, fields, models, tools
import logging

_logger = logging.getLogger(__name__)


class ShHelpdeskTicket(models.Model):
    _name = 'sh.helpdesk.ticket'
    _inherit = ['sh.helpdesk.ticket','mail.thread.cc']

    def _prepare_name_email_data(self, row_data):
        """
        Prepare name and email data from a list of tuples.

        Args:
            row_data (list): List of (name, email) tuples.

        Returns:
            list: A list of dictionaries, each containing a name and an email.
        """
        name_email_data = []
        for (name, email) in tools.mail.email_split_tuples(row_data):
            name_email_data.append({'name': name, 'email': email})
        return name_email_data

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):

        result = super(ShHelpdeskTicket, self.with_context(mail_post_autofollow=True)).message_post(**kwargs)
        try:
            # Define the 'note' subtype id
            subtype_comment = self.env.ref('mail.mt_note').id
            user = self.env.user
            # Check if the result's subtype is not 'note'
            if not user._is_internal() or user.id==1:
                # Check if the result is not authored by the current user or a guest
                if not result.is_current_user_or_guest_author:
                    # Update the state and replied_date if conditions are met
                    self.write({'state': 'customer_replied'})
                elif result.author_id.id==2: #if on sh_receive_email_seeing_ticket Configuration Not change ( the purpose is only for add lognote 'Ticket viewed by customer Customername' )
                    pass
                else:
                    # Update the state and replied_date if conditions are met
                    self.write({'state': 'staff_replied', 'replied_date': fields.Datetime.now()})

            # Check if the ticket has a team with an alias name and domain
            if self.team_id and self.team_id.alias_name and self.team_id.alias_domain:
                # Create a formatted email address from the team's alias name and domain
                email = str(self.team_id.alias_name) + '@' + str(self.team_id.alias_domain)
                email_formatted = tools.formataddr((self.team_id.name or u"False", email))

                # Search for a mail server with the same SMTP user as the team's alias email
                mail_server_id = self.env['ir.mail_server'].search([('smtp_user', '=', email)], limit=1)

                # If no mail server is found, use the first active mail server
                if not mail_server_id:
                    mail_server_id = self.env['ir.mail_server'].search([('active', '=', True), ('sequence', '>', 0)], order="sequence", limit=1)

                    # Update the result with the email_from and mail_server_id
                if mail_server_id:
                    result.write({'email_from': email_formatted, 'mail_server_id': mail_server_id.id})
        except Exception as e:
            _logger.exception("Error when Sending Email (message_post) for Helpdesk Ticket: %s", e)
            return result
        return result


    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """
        Overrides mail_thread message_new that is called by the mail gateway
        through message_process. This override updates the document according to the email.

        Args:
            msg_dict (dict): Dictionary containing email message details.
            custom_values (dict, optional): Custom values to be added.

        Returns:
            object: The created message object.
        """

        try:
            partner_ids = []
            get_outgoing_server_all = self.env['ir.mail_server'].search([('active', '=', True)])

            incoming_email = False
            if custom_values is not None:
                if 'team_id' in custom_values:
                    team_id = self.env['sh.helpdesk.team'].browse(custom_values.get('team_id'))
                    if team_id and team_id.alias_name and team_id.alias_domain:
                        alias_email = str(team_id.alias_name) + '@' + str(team_id.alias_domain)
                        incoming_email = alias_email

            if 'to' in msg_dict:
                name_email_data = self._prepare_name_email_data(msg_dict.get('to'))
                for each_email_data in name_email_data:
                    email_name = each_email_data['name']
                    email_address = each_email_data['email'].lower()
                    if email_address!=incoming_email and get_outgoing_server_all and email_address not in get_outgoing_server_all.mapped('smtp_user'):
                        partner_id = self.env['res.partner'].search([('email', '=', email_address)], limit=1)
                        if partner_id:
                            partner_ids.append(partner_id.id)
                        else:
                            partner_id = self.env['res.partner'].create({'name': email_name or email_address, 'email': email_address})
                            partner_ids.append(partner_id.id)

            if 'cc' in msg_dict:
                name_cc_data = self._prepare_name_email_data(msg_dict.get('cc'))
                for each_cc_data in name_cc_data:
                    cc_name = each_cc_data['name']
                    cc_address = each_cc_data['email'].lower()
                    if cc_address!=incoming_email and get_outgoing_server_all and cc_address not in get_outgoing_server_all.mapped('smtp_user'):
                        partner_id = self.env['res.partner'].search([('email', '=', cc_name)], limit=1)
                        if partner_id:
                            partner_ids.append(partner_id.id)
                        else:
                            partner_id = self.env['res.partner'].create({'name': cc_name, 'email': cc_address})
                            partner_ids.append(partner_id.id)

            defaults = {
                'name': msg_dict.get('subject') or _("No Subject"),
                'email': msg_dict.get('from'),
                'partner_id': msg_dict.get('author_id', False),
                'description': msg_dict.get('body'),
                'email_subject': msg_dict.get('subject') or _("No Subject"),
                'state': 'customer_replied',
                'replied_date': msg_dict.get('date')
            }

            if custom_values is None:
                custom_values = {}
            if custom_values.get('team_id'):
                team_id = self.env['sh.helpdesk.team'].browse(custom_values.get('team_id'))
                if team_id:
                    defaults.update({
                        'team_id': team_id.id,
                        'team_head': team_id.team_head.id
                    })

            result = super(ShHelpdeskTicket, self).message_new(msg_dict, custom_values=defaults)

            if partner_ids:
                result.message_subscribe(partner_ids=partner_ids)

        except Exception as e:
            _logger.exception("Error when Fetch Email (message_new) for Helpdesk Ticket: %s", e)

            return super(ShHelpdeskTicket, self).message_new(msg_dict, custom_values=defaults)
        return result

    def _message_post_after_hook(self, message, msg_vals):
        if self.email and not self.partner_id:
            # we consider that posting a message with a specified recipient (not a follower, a specific one)
            # on a document without customer means that it was created through the chatter using
            # suggested recipients. This heuristic allows to avoid ugly hacks in JS.
            new_partner = message.partner_ids.filtered(
                lambda partner: partner.email == self.email)
            if new_partner:
                self.search([
                    ('partner_id', '=', False),
                    ('email', '=', new_partner.email),
                ]).write({'partner_id': new_partner.id})

        return super(ShHelpdeskTicket,self)._message_post_after_hook(message, msg_vals)
