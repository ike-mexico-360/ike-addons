# hooks.py
import re
import os
import pickle
import json
import logging
from odoo import tools
from odoo.http import root

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Load existing sessions when installing"""
    cr = env.cr

    # Get session directory
    session_store = root.session_store
    session_dir = getattr(session_store, 'path', '')

    if not session_dir or not os.path.exists(session_dir):
        session_dir = os.path.join(tools.config['data_dir'], 'sessions')

    if not os.path.exists(session_dir):
        _logger.warning(f"[HOOK] Session directory not found: {session_dir}")
        return

    _logger.info(f"[HOOK] Searching for sessions in: {session_dir}")

    processed = 0
    errors = 0

    # Cache existing users to avoid querying the database for each file.
    cr.execute("SELECT id FROM res_users")
    existing_user_ids = {row[0] for row in cr.fetchall()}

    # Use os.walk to search all subdirectories
    for root_dir, dirs, files in os.walk(session_dir):
        _logger.debug(f"[HOOK] Examining directory: {root_dir}")

        for filename in files:
            # Skip temporary/hidden files
            if filename.startswith('.') or filename.endswith('~'):
                continue

            # Odoo session files usually have long names
            if len(filename) < 20:
                _logger.debug(f"[HOOK] Skipping short file: {filename}")
                continue

            file_path = os.path.join(root_dir, filename)
            uid = None

            try:
                _logger.debug(f"[HOOK] Processing file: {filename}")

                with open(file_path, 'rb') as f:
                    content = f.read()

                    if not content:
                        _logger.debug(f"[HOOK] Empty file: {filename}")
                        continue

                    _logger.debug(f"[HOOK] File size: {len(content)} bytes")

                    # Try Pickle first (Odoo's standard format)
                    try:
                        data = pickle.loads(content)
                        uid = data.get('uid') or data.get('_uid')
                        _logger.debug(f"[HOOK] Pickle successful - UID: {uid}")
                    except Exception as pickle_error:
                        _logger.debug(f"[HOOK] Pickle failed: {pickle_error}")

                        # Try JSON
                        try:
                            decoded = content.decode('utf-8', errors='ignore')
                            data = json.loads(decoded)
                            uid = data.get('uid') or data.get('_uid')
                            _logger.debug(f"[HOOK] JSON successful - UID: {uid}")
                        except Exception as json_error:
                            _logger.debug(f"[HOOK] JSON failed: {json_error}")

                            # Direct search in bytes/string
                            try:
                                # Look for common patterns
                                content_str = content.decode('utf-8', errors='ignore')

                                # Pattern: "uid": 2
                                matches = re.findall(r'"uid"\s*:\s*(\d+)', content_str)
                                if matches:
                                    uid = int(matches[0])
                                    _logger.debug(f"[HOOK] Regex found UID: {uid}")
                                else:
                                    # Alternative pattern: 'uid': 2
                                    matches = re.findall(r"'uid'\s*:\s*(\d+)", content_str)
                                    if matches:
                                        uid = int(matches[0])
                                        _logger.debug(f"[HOOK] Alternative regex UID: {uid}")
                            except Exception as regex_error:
                                _logger.debug(f"[HOOK] Regex failed: {regex_error}")

                if uid:
                    # Get file timestamps
                    try:
                        # CRITICAL VALIDATION: Does the user exist in Odoo?
                        if int(uid) not in existing_user_ids:
                            _logger.debug(f"[HOOK] Skipping session {filename}: User {uid} does not exist in res_user")
                            continue
                        # Check if already exists
                        cr.execute("SELECT id FROM custom_res_users_session WHERE session_id = %s", (filename,))
                        exists = cr.fetchone()

                        if not exists:
                            # Insert into table
                            cr.execute("""
                                INSERT INTO custom_res_users_session
                                (user_id, session_id, file_path)
                                VALUES (%s, %s, %s)
                            """, (int(uid), filename, file_path))

                            processed += 1
                            _logger.debug(f"[HOOK] Session inserted: {filename} for user {uid}")
                        else:
                            _logger.debug(f"[HOOK] Session already exists: {filename}")

                    except Exception as insert_error:
                        errors += 1
                        _logger.error(f"[HOOK] Error inserting session {filename}: {insert_error}")
                else:
                    _logger.debug(f"[HOOK] Could not extract UID from: {filename}")

            except Exception as e:
                errors += 1
                _logger.error(f"[HOOK] Error processing {filename}: {e}")
                continue

    _logger.info(f"[HOOK] Loaded {processed} existing sessions, {errors} errors")

    # Also create indexes if they don't exist
    try:
        _logger.info("[HOOK] Creating indexes...")
        cr.execute("""
            CREATE INDEX IF NOT EXISTS custom_session_user_id_idx
            ON custom_res_users_session (user_id)
        """)
        cr.execute("""
            CREATE INDEX IF NOT EXISTS custom_session_session_id_idx
            ON custom_res_users_session (session_id)
        """)
        _logger.info("[HOOK] Indexes created successfully")
    except Exception as e:
        _logger.warning(f"[HOOK] Error creating indexes: {e}")