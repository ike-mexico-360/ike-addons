# -*- coding: utf-8 -*-
import logging
import os
from datetime import datetime
from odoo.modules.registry import Registry
import odoo
from odoo import models, fields, api
from odoo.http import GeoIP, request, root

from contextlib import nullcontext

from odoo.tools import SQL
from odoo.tools.translate import _
import logging

_logger = logging.getLogger(__name__)


class CustomUserSession(models.Model):
    _name = 'custom.res.users.session'
    _description = 'User Session Tracking'

    user_id = fields.Many2one('res.users', required=True, index=True)
    session_id = fields.Char(required=True, index=True)
    file_path = fields.Char()


class ResDeviceLog(models.Model):
    _inherit = 'res.device.log'

    @api.model
    def _update_device(self, request):
        """
            Must be called when we want to update the device for the current request.
            Passage through this method must leave a "trace" in the session.

            :param request: Request or WebsocketRequest object
        """
        trace = request.session.update_trace(request)
        if not trace:
            return

        geoip = GeoIP(trace['ip_address'])
        user_id = request.session.uid
        session_identifier = request.session.sid[:42]

        if self.env.cr.readonly:
            self.env.cr.rollback()
            cursor = self.env.registry.cursor(readonly=False)
        else:
            cursor = nullcontext(self.env.cr)
        with cursor as cr:
            cr.execute(SQL("""
                INSERT INTO res_device_log (session_identifier, platform, browser, ip_address, country, city, device_type, user_id, first_activity, last_activity, revoked)
                VALUES (%(session_identifier)s, %(platform)s, %(browser)s, %(ip_address)s, %(country)s, %(city)s, %(device_type)s, %(user_id)s, %(first_activity)s, %(last_activity)s, %(revoked)s)
            """,
                session_identifier=session_identifier,
                platform=trace['platform'],
                browser=trace['browser'],
                ip_address=trace['ip_address'],
                country=geoip.get('country_name'),
                city=geoip.get('city'),
                device_type='mobile' if self._is_mobile(trace['platform']) else 'computer',
                user_id=user_id,
                first_activity=datetime.fromtimestamp(trace['first_activity']),
                last_activity=datetime.fromtimestamp(trace['last_activity']),
                revoked=False,
            ))
            self._update_custom_res_users_session(request, user_id, session_identifier)
        _logger.info("User %d inserts device log (%s)", user_id, session_identifier)
        # return result

    @api.model
    def _update_custom_res_users_session(self, request, user_id, session_identifier):
        """
        Updates or creates a record in custom_res_users_session
        """
        full_session_id = request.session.sid  # Full ID
        file_path = ""
        cr = self.env.cr

        try:
            session_store = root.session_store
            session_dir = getattr(session_store, 'path', '')
            # Try to build the file path
            if session_dir and full_session_id:
                # Check if the file exists with the full ID
                possible_file = os.path.join(session_dir, full_session_id)
                if os.path.exists(possible_file):
                    file_path = possible_file
                else:
                    # Look for files that might be this session
                    for filename in os.listdir(session_dir):
                        if full_session_id in filename or filename.startswith(full_session_id[:20]):
                            file_path = os.path.join(session_dir, filename)
                            break
        except Exception as e:
            _logger.debug("Could not get session store: %s", e)

        # Check if it already exists in your table
        cr.execute("""
            SELECT id FROM custom_res_users_session
            WHERE session_id = %s AND user_id = %s
        """, (full_session_id, user_id))

        exists = cr.fetchone()

        if not exists:
            # INSERT: Create new record
            cr.execute("""
                INSERT INTO custom_res_users_session
                (user_id, session_id, file_path)
                VALUES (%s, %s, %s)
            """, (user_id, full_session_id, file_path))
            _logger.info("Created custom session: %s", full_session_id[:20])
        _logger.info("User %d inserts device log (%s)", user_id, session_identifier)


class ResUsers(models.Model):
    _inherit = "res.users"

    @classmethod
    def _login(cls, db, credential, user_agent_env=None):
        """
        Login override - Closes all previous sessions using the table
        """
        _logger.info("=== STARTING LOGIN WITH SESSION MANAGEMENT ===")

        # 1. Normal Odoo login
        auth_info = super()._login(db, credential, user_agent_env=user_agent_env)

        if auth_info and auth_info.get("uid"):
            uid = auth_info["uid"]
            _logger.warning(f"User {uid} logging in - closing previous sessions")

            try:
                # Get all user sessions FROM THE TABLE
                registry = Registry(db)
                with registry.cursor() as cr:
                    env = api.Environment(cr, odoo.SUPERUSER_ID, {})

                    # Search in the table (NOT in the filesystem!)
                    active_sessions = env['custom.res.users.session'].search([
                        ('user_id', '=', uid),
                    ])

                    _logger.info(f"Found {len(active_sessions)} active sessions in the table")

                    # 3. Close each session using native method
                    session_store = root.session_store
                    closed_count = 0

                    for session in active_sessions:
                        try:
                            session_id = session.session_id
                            _logger.info(f"Closing session: {session_id}")

                            # Close with Odoo's native method
                            odoo_session = session_store.get(session_id)
                            if odoo_session:
                                odoo_session.logout(keep_db=True)
                                session_store.save(odoo_session)
                                _logger.info(f"Session closed in Odoo: {session_id}")

                            # Delete physical file if it exists
                            session_dir = getattr(session_store, 'path', None)
                            if session_dir and session_id:
                                session_file = os.path.join(session_dir, session_id)
                                if os.path.exists(session_file):
                                    os.remove(session_file)
                                    _logger.info(f"File deleted: {session_id}")

                            # Mark as inactive in the table
                            session.unlink()
                            closed_count += 1

                        except Exception as e:
                            _logger.error(f"Error closing session {session.session_id}: {e}")

                    _logger.warning(f"Closed {closed_count} previous sessions for user {uid}")

                _logger.info("=== LOGIN COMPLETED SUCCESSFULLY ===")

            except Exception as e:
                _logger.error(f"ERROR in session management: {e}")

        return auth_info
