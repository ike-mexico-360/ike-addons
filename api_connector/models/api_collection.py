from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import json
import logging
import base64

_logger = logging.getLogger(__name__)


class ApiCollection(models.Model):
    _name = 'api.collection'
    _description = 'API Collection - Group related endpoints'
    _order = 'name'

    name = fields.Char(
        string='Collection Name',
        required=True,
        help='Name for this collection of API endpoints'
    )

    description = fields.Text(
        string='Description',
        help='Description of this API collection'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Enable/disable this collection'
    )

    def write(self, vals):
        """Archive/unarchive associated connectors when collection is archived/unarchived"""
        result = super().write(vals)

        if 'active' in vals:
            # Archive/unarchive all associated connectors
            for collection in self:
                collection.connector_ids.write({'active': vals['active']})

        return result

    # === SHARED CONFIGURATION ===
    base_url = fields.Char(
        string='Base URL',
        help='Default base URL for all endpoints in this collection'
    )

    # === SHARED AUTHENTICATION ===
    auth_type = fields.Selection([
        ('none', 'No Authentication'),
        ('basic', 'Basic Auth'),
        ('bearer', 'Bearer Token'),
        ('api_key', 'API Key'),
        ('oauth2', 'OAuth 2.0')
    ], string='Default Authentication', default='none')

    auth_username = fields.Char(
        string='Username',
        help='Default username for Basic Auth'
    )

    auth_password = fields.Char(
        string='Password',
        help='Default password for Basic Auth'
    )

    auth_token = fields.Char(
        string='Bearer Token / API Key',
        help='Default token for Bearer or API Key authentication'
    )

    auth_header_name = fields.Char(
        string='API Key Header Name',
        default='X-API-Key',
        help='Default header name for API Key'
    )

    # OAuth 2.0 fields
    oauth_client_id = fields.Char(
        string='OAuth Client ID',
        help='OAuth 2.0 Client ID for this collection'
    )

    oauth_client_secret = fields.Char(
        string='OAuth Client Secret',
        help='OAuth 2.0 Client Secret for this collection'
    )

    oauth_token_url = fields.Char(
        string='OAuth Token URL',
        help='OAuth 2.0 Token URL for this collection'
    )

    oauth_scope = fields.Char(
        string='OAuth Scope',
        help='OAuth 2.0 Scope for this collection'
    )

    oauth_authorization_url = fields.Char(
        string='Authorization URL',
        help='OAuth 2.0 Authorization URL'
    )

    oauth_access_token = fields.Char(
        string='Access Token',
        readonly=True,
        help='Current OAuth 2.0 Access Token'
    )

    oauth_refresh_token = fields.Char(
        string='Refresh Token',
        readonly=True,
        help='OAuth 2.0 Refresh Token'
    )

    oauth_token_expires_at = fields.Datetime(
        string='Token Expires At',
        readonly=True,
        help='When the current access token expires'
    )

    # === SHARED HEADERS ===
    default_headers = fields.Text(
        string='Default Headers',
        help='JSON format: {"Content-Type": "application/json"}\nApplied to all endpoints in collection'
    )

    # === COLLECTION VARIABLES ===
    collection_variables = fields.Text(
        string='Collection Variables',
        help='JSON format: {"api_version": "v2", "environment": "prod"}\nUsed in endpoint URLs and bodies'
    )

    # === RELATIONSHIPS ===
    connector_ids = fields.One2many(
        'api.connector',
        'collection_id',
        string='API Endpoints',
        help='Endpoints in this collection'
    )

    # === COMPUTED FIELDS ===
    connector_count = fields.Integer(
        string='Endpoints Count',
        compute='_compute_connector_count',
        store=True
    )

    total_calls = fields.Integer(
        string='Total Calls',
        compute='_compute_collection_stats',
        store=True
    )

    success_rate = fields.Float(
        string='Collection Success Rate',
        compute='_compute_collection_stats',
        store=True
    )

    @api.depends('connector_ids')
    def _compute_connector_count(self):
        """Compute number of endpoints in collection"""
        for record in self:
            record.connector_count = len(record.connector_ids)

    @api.depends('connector_ids.total_calls', 'connector_ids.success_calls')
    def _compute_collection_stats(self):
        """Compute collection-wide statistics"""
        for record in self:
            connectors = record.connector_ids
            if connectors:
                total_calls = sum(connectors.mapped('total_calls'))
                total_success = sum(connectors.mapped('success_calls'))

                record.total_calls = total_calls
                if total_calls > 0:
                    record.success_rate = total_success / total_calls
                else:
                    record.success_rate = 0.0
            else:
                record.total_calls = 0
                record.success_rate = 0.0

    @api.constrains('default_headers')
    def _check_default_headers(self):
        """Validate default headers JSON format"""
        for record in self:
            if record.default_headers:
                try:
                    json.loads(record.default_headers)
                except json.JSONDecodeError:
                    raise ValidationError(_("Default headers must be valid JSON format"))

    @api.constrains('collection_variables')
    def _check_collection_variables(self):
        """Validate collection variables JSON format"""
        for record in self:
            if record.collection_variables:
                try:
                    variables = json.loads(record.collection_variables)
                    if not isinstance(variables, dict):
                        raise ValidationError(_("Collection variables must be a JSON object (dictionary)"))
                except json.JSONDecodeError:
                    raise ValidationError(_("Collection variables must be valid JSON format"))

    def action_view_connectors(self):
        """Open connectors in this collection"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Endpoints in %s') % self.name,
            'res_model': 'api.connector',
            'view_mode': 'list,form',
            'domain': [('collection_id', '=', self.id)],
            'context': {
                'default_collection_id': self.id,
                'search_default_collection_id': self.id,
            }
        }

    def create_connector_from_collection(self):
        """Create a new connector with collection defaults"""
        self.ensure_one()

        # Prepare default values from collection
        default_values = {
            'collection_id': self.id,
            'base_url': self.base_url,
            'auth_type': self.auth_type,
            'auth_username': self.auth_username,
            'auth_password': self.auth_password,
            'auth_token': self.auth_token,
            'auth_header_name': self.auth_header_name,
            'oauth_client_id': self.oauth_client_id,
            'oauth_client_secret': self.oauth_client_secret,
            'oauth_token_url': self.oauth_token_url,
            'oauth_scope': self.oauth_scope,
            'custom_headers': self.default_headers,
        }

        # Remove None values
        default_values = {k: v for k, v in default_values.items() if v}

        return {
            'type': 'ir.actions.act_window',
            'name': _('New Endpoint in %s') % self.name,
            'res_model': 'api.connector',
            'view_mode': 'form',
            'target': 'current',
            'context': {'default_%s' % k: v for k, v in default_values.items()}
        }

    def get_collection_variables_dict(self):
        """Get collection variables as dictionary"""
        self.ensure_one()
        if not self.collection_variables:
            return {}

        try:
            return json.loads(self.collection_variables)
        except json.JSONDecodeError:
            _logger.warning(f"Invalid collection variables JSON for collection {self.name}")
            return {}

    @api.model
    def create_from_template(self, name, base_url, auth_type='none', **kwargs):
        """Helper to create collection from template"""
        values = {
            'name': name,
            'base_url': base_url,
            'auth_type': auth_type,
        }
        values.update(kwargs)
        return self.create(values)

    @api.model
    def fix_success_rates(self):
        collections = self.search([('success_rate', '>', 1.0)])
        for collection in collections:
            # Force recomputation
            collection._compute_collection_stats()
            _logger.info(f"Fixed success rate for collection {collection.name}")
        return True

    def get_oauth_token(self):
        """Get OAuth 2.0 access token using client credentials flow"""
        self.ensure_one()

        if self.auth_type != 'oauth2':
            raise UserError(_("This method is only available for OAuth 2.0 authentication"))

        if not all([self.oauth_client_id, self.oauth_client_secret, self.oauth_token_url]):
            raise UserError(
                _("OAuth 2.0 configuration incomplete. Please fill Client ID, Client Secret, and Token URL."))

        try:
            import requests
            from datetime import datetime, timedelta

            # Prepare token request
            token_data = {
                'grant_type': 'client_credentials',
                'client_id': self.oauth_client_id,
                'client_secret': self.oauth_client_secret,
            }

            if self.oauth_scope:
                token_data['scope'] = self.oauth_scope

            # Make token request
            response = requests.post(
                self.oauth_token_url,
                data=token_data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=30
            )

            if response.status_code == 200:
                token_info = response.json()
                access_token = token_info.get('access_token')
                refresh_token = token_info.get('refresh_token')
                expires_in = token_info.get('expires_in', 3600)  # Default 1 hour

                if access_token:
                    # Calculate expiration time
                    expires_at = datetime.now() + timedelta(seconds=int(expires_in))

                    # Update collection with new tokens
                    self.write({
                        'oauth_access_token': access_token,
                        'oauth_refresh_token': refresh_token,
                        'oauth_token_expires_at': expires_at,
                        'auth_token': access_token,  # Also update auth_token for inheritance
                    })

                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Collection OAuth Token Retrieved Successfully'),
                            'message': f'Access Token: {access_token[:20]}... | Expires: {expires_at.strftime("%Y-%m-%d %H:%M")} | Scope: {len(token_info.get("scope", "").split())} permissions',
                            'type': 'success',
                            'sticky': True,
                        }
                    }
                else:
                    raise UserError(_("No access token received from OAuth provider"))
            else:
                error_detail = response.text
                try:
                    error_json = response.json()
                    error_detail = error_json.get('error_description', error_json.get('error', response.text))
                except BaseException:
                    pass

                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Collection OAuth Token Request Failed'),
                        'message': f'Status: {response.status_code} | Error: {error_detail}',
                        'type': 'danger',
                        'sticky': True,
                    }
                }

        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Collection OAuth Error'),
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def export_config(self):
        """Export collection configuration to JSON"""
        self.ensure_one()

        # Fields to export (excluding computed, related, and system fields)
        export_fields = [
            'name', 'active', 'description', 'base_url', 'auth_type',
            'auth_username', 'auth_password', 'auth_token', 'oauth_client_id',
            'oauth_client_secret', 'oauth_authorization_url', 'oauth_token_url',
            'oauth_scope', 'auth_header_name', 'default_headers', 'collection_variables'
        ]

        config = {}
        for field in export_fields:
            if hasattr(self, field):
                value = getattr(self, field)
                if value:  # Only export non-empty values
                    config[field] = value

        # Export connectors configuration
        connectors_config = []
        for connector in self.connector_ids:
            connector_fields = [
                'name', 'active', 'api_type', 'method', 'endpoint_path',
                'endpoint_variables', 'auth_type', 'auth_username',
                'auth_password', 'auth_token', 'oauth_client_id', 'oauth_client_secret',
                'oauth_authorization_url', 'oauth_token_url', 'oauth_scope',
                'auth_header_name', 'custom_headers', 'request_body_type',
                'request_body', 'form_data', 'file_field_name', 'expected_response_type',
                'timeout', 'verify_ssl', 'use_collection_url'
            ]

            connector_config = {}
            for field in connector_fields:
                if hasattr(connector, field):
                    value = getattr(connector, field)
                    if value:  # Only export non-empty values
                        connector_config[field] = value

            if connector_config:  # Only add if has configuration
                connectors_config.append(connector_config)

        if connectors_config:
            config['connectors'] = connectors_config

        # Add metadata
        config['_metadata'] = {
            'export_date': fields.Datetime.now().isoformat(),
            'export_user': self.env.user.name,
            'odoo_version': '18.0',
            'module_version': '1.0.0',
            'type': 'api_collection',
            'connectors_count': len(connectors_config)
        }

        # Create attachment with JSON content
        json_content = json.dumps(config, indent=2, ensure_ascii=False)
        attachment = self.env['ir.attachment'].create({
            'name': f'api_collection_{self.name}_{fields.Date.today()}.json',
            'datas': base64.b64encode(json_content.encode('utf-8')),
            'mimetype': 'application/json',
            'res_model': self._name,
            'res_id': self.id,
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

    @api.model
    def import_config(self, json_data):
        """Import collection configuration from JSON"""
        try:
            if isinstance(json_data, str):
                config = json.loads(json_data)
            else:
                config = json_data
        except json.JSONDecodeError as e:
            raise UserError(_("Invalid JSON format: %s") % str(e))

        # Validate metadata
        if '_metadata' not in config or config['_metadata'].get('type') != 'api_collection':
            raise UserError(_("Invalid configuration file: not an API collection export"))

        # Remove metadata and connectors for collection creation
        metadata = config.pop('_metadata', {})
        connectors_config = config.pop('connectors', [])

        # Validate required fields
        if 'name' not in config:
            raise UserError(_("Configuration must contain a 'name' field"))

        # Create the collection
        collection = self.create(config)

        # Create connectors
        created_connectors = []
        for connector_config in connectors_config:
            connector_config['collection_id'] = collection.id
            # Set use_collection_url to True for imported connectors
            if 'use_collection_url' not in connector_config:
                connector_config['use_collection_url'] = True

            connector = self.env['api.connector'].create(connector_config)
            created_connectors.append(connector)

        message = f"Collection '{collection.name}' imported successfully"
        if created_connectors:
            message += f" with {len(created_connectors)} connectors"

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Import Successful'),
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Imported Collection: %s') % collection.name,
                    'res_model': 'api.collection',
                    'res_id': collection.id,
                    'view_mode': 'form',
                    'target': 'current',
                }
            }
        }
