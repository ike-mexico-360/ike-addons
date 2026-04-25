from odoo import models, api, _
import logging

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _message_compute_author(self, author_id=None, email_from=None, raise_on_email=True):
        """
        Adjusts the message author if the user belongs to the coordinators group
        and no sender information has been specified.
        """
        # If sender data is missing (author or email)
        if not author_id or not email_from:
            # Check the current user's security group
            if self.env.user.has_group('custom_master_catalog.custom_group_event_coordinator'):

                # Retrieve the target name from System Parameters using the specific key
                param_obj = self.env['ir.config_parameter'].sudo()
                target_name = param_obj.get_param('default.usermailcoordinatorcds')

                if target_name:
                    # Search for the user by the name defined in the parameter
                    # and validate against their specific login/email
                    target_user = self.env['res.users'].sudo().search([
                        ('name', '=', target_name)
                    ], limit=1)

                    if target_user:
                        # Override author and email from the found user's partner record
                        author_id = target_user.partner_id.id
                        email_from = target_user.partner_id.email_formatted
                        _logger.info("Sender forced via default.usermailcoordinatorcds: %s", target_name)

        # Return to Odoo's standard flow with the injected values
        return super(MailThread, self)._message_compute_author(
            author_id=author_id,
            email_from=email_from,
            raise_on_email=raise_on_email
        )
