from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
from datetime import datetime, timedelta
import base64


_logger = logging.getLogger(__name__)


class ApiConnector(models.Model):
    _name = 'api.connector'
    _description = 'API Connector - Outbound API Configuration'
    _order = 'name'

    name = fields.Char(
        string='Connection Name',
        required=True,
        help='Friendly name for this API connection'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Enable/disable this API connection'
    )

    is_system_critical = fields.Boolean(
        string='System Critical',
        default=False,
        help='Protect this route from accidental deletion - requires special confirmation'
    )

    collection_id = fields.Many2one(
        'api.collection',
        string='Collection',
        help='Collection this endpoint belongs to'
    )

    # === BASIC CONFIGURATION ===
    use_collection_url = fields.Boolean(
        string='Use Collection URL',
        default=True,
        help='Use the base URL from the collection'
    )

    base_url = fields.Char(
        string='Base URL',
        help='Base URL for the API (e.g., https://api.example.com)'
    )

    api_type = fields.Selection([
        ('rest', 'REST API'),
        ('jsonrpc', 'JSON-RPC'),
        ('graphql', 'GraphQL'),
        ('soap', 'SOAP/XML')
    ], string='API Type', default='rest', required=True)

    method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('PATCH', 'PATCH'),
        ('DELETE', 'DELETE')
    ], string='HTTP Method', default='GET', required=True)

    endpoint_path = fields.Char(
        string='Endpoint Path',
        help='Path to append to base URL (e.g., /api/v1/users or /api/v2/saleorder/read/{id})'
    )

    # Endpoint-specific variables
    endpoint_variables = fields.Text(
        string='Endpoint Variables',
        help='JSON format for endpoint-specific variables: {"user_id": "123", "filter": "active"}\nOverrides collection variables'
    )

    # === AUTHENTICATION ===
    auth_type = fields.Selection([
        ('inherit', 'Inherit from Collection'),
        ('none', 'No Authentication'),
        ('basic', 'Basic Auth'),
        ('bearer', 'Bearer Token'),
        ('api_key', 'API Key'),
        ('oauth2', 'OAuth 2.0')
    ], string='Authentication Type', default='inherit', required=True)

    auth_username = fields.Char(
        string='Username',
        help='Username for Basic Auth'
    )

    auth_password = fields.Char(
        string='Password',
        help='Password for Basic Auth'
    )

    auth_token = fields.Char(
        string='Bearer Token / API Key',
        help='Token for Bearer or API Key authentication'
    )

    # OAuth 2.0 specific fields
    oauth_client_id = fields.Char(
        string='Client ID',
        help='OAuth 2.0 Client ID'
    )

    oauth_client_secret = fields.Char(
        string='Client Secret',
        help='OAuth 2.0 Client Secret'
    )

    oauth_authorization_url = fields.Char(
        string='Authorization URL',
        help='OAuth 2.0 Authorization URL (e.g., https://api.example.com/oauth/authorize)'
    )

    oauth_token_url = fields.Char(
        string='Token URL',
        help='OAuth 2.0 Token URL (e.g., https://api.example.com/oauth/token)'
    )

    oauth_scope = fields.Char(
        string='Scope',
        help='OAuth 2.0 Scope (e.g., read write)'
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

    # Response fields for displaying API results
    last_response_data = fields.Text(
        string='Last Response Data',
        readonly=True,
        help='Response data from the last API call'
    )

    last_response_status = fields.Integer(
        string='Last Response Status',
        readonly=True,
        help='HTTP status code from the last API call'
    )

    last_response_time = fields.Float(
        string='Last Response Time (ms)',
        readonly=True,
        help='Execution time of the last API call in milliseconds'
    )

    last_response_success = fields.Boolean(
        string='Last Response Success',
        readonly=True,
        help='Whether the last API call was successful'
    )

    last_response_error = fields.Text(
        string='Last Response Error',
        readonly=True,
        help='Error message from the last API call if any'
    )

    auth_header_name = fields.Char(
        string='API Key Header Name',
        default='X-API-Key',
        help='Header name for API Key (e.g., X-API-Key, Authorization)'
    )

    # === HEADERS ===
    custom_headers = fields.Text(
        string='Custom Headers',
        help='JSON format: {"Content-Type": "application/json", "Accept": "application/json"}'
    )

    # === REQUEST BODY ===
    request_body_type = fields.Selection([
        ('none', 'No Body'),
        ('json', 'JSON'),
        ('form', 'Form Data (application/x-www-form-urlencoded)'),
        ('form_multipart', 'Form Data (multipart/form-data)'),
        ('xml', 'XML'),
        ('raw', 'Raw Text'),
        ('binary', 'Binary (base64)')
    ], string='Request Body Type', default='none')

    request_body = fields.Text(
        string='Request Body',
        help='Request body content (JSON, XML, raw text, or base64 for binary)'
    )

    # Form data fields
    form_data = fields.Text(
        string='Form Data',
        help='JSON format for form data: {"key1": "value1", "key2": "value2"}'
    )

    # File Upload Configuration
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Files to Upload',
        help='Select files to upload with the request (for multipart form data)'
    )
    file_field_name = fields.Char(
        string='File Field Name',
        default='ufile',
        help='Name of the file field in the form (e.g., "ufile", "file", "attachment")'
    )

    # === RESPONSE HANDLING ===
    expected_response_type = fields.Selection([
        ('json', 'JSON'),
        ('xml', 'XML'),
        ('text', 'Plain Text'),
        ('binary', 'Binary')
    ], string='Expected Response Type', default='json')

    # === SETTINGS ===
    timeout = fields.Integer(
        string='Timeout (seconds)',
        default=30,
        help='Request timeout in seconds'
    )

    verify_ssl = fields.Boolean(
        string='Verify SSL Certificate',
        default=True,
        help='Verify SSL certificate for HTTPS requests'
    )

    # === MONITORING ===
    total_calls = fields.Integer(
        string='Total Calls',
        readonly=True,
        default=0
    )

    success_calls = fields.Integer(
        string='Successful Calls',
        readonly=True,
        default=0
    )

    last_call_date = fields.Datetime(
        string='Last Call',
        readonly=True
    )

    success_rate = fields.Float(
        string='Success Rate (%)',
        compute='_compute_success_rate',
        store=True
    )

    # === COMPUTED FIELDS ===
    full_url = fields.Char(
        string='Full URL',
        compute='_compute_full_url',
        store=True
    )

    @api.onchange('api_type')
    def _onchange_api_type(self):
        """Auto-adjust method when API type changes (UI only)"""
        if self.api_type in ['jsonrpc', 'graphql', 'soap']:
            self.method = 'POST'
            # Also set appropriate request body type for JSON-RPC
            if self.api_type == 'jsonrpc':
                self.request_body_type = 'json'

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set correct method for non-REST APIs"""
        for vals in vals_list:
            if vals.get('api_type') in ['jsonrpc', 'graphql', 'soap']:
                vals['method'] = 'POST'
                if vals.get('api_type') == 'jsonrpc':
                    vals.setdefault('request_body_type', 'json')
        return super().create(vals_list)

    def write(self, vals):
        """Override write to set correct method when api_type changes"""
        if 'api_type' in vals:
            if vals['api_type'] in ['jsonrpc', 'graphql', 'soap']:
                vals['method'] = 'POST'
                if vals['api_type'] == 'jsonrpc':
                    vals.setdefault('request_body_type', 'json')
        return super().write(vals)

    @api.depends('use_collection_url', 'base_url', 'endpoint_path',
                 'endpoint_variables', 'collection_id.base_url', 'collection_id.collection_variables')
    def _compute_full_url(self):
        """Compute the full URL with collection inheritance and variable substitution"""
        for record in self:
            # Determine base URL
            if record.use_collection_url and record.collection_id and record.collection_id.base_url:
                base = record.collection_id.base_url
            else:
                base = record.base_url or ''

            base = base.rstrip('/') if base else ''
            path = (record.endpoint_path or '').lstrip('/')

            # Build basic URL
            if base and path:
                url = f"{base}/{path}"
            else:
                url = base or path or ''

            # Get all variables (collection + endpoint)
            all_variables = {}

            # Start with collection variables
            if record.collection_id and record.collection_id.collection_variables:
                try:
                    collection_vars = json.loads(record.collection_id.collection_variables)
                    all_variables.update(collection_vars)
                except json.JSONDecodeError:
                    pass

            # Add endpoint-specific variables (override collection variables)
            if record.endpoint_variables:
                try:
                    endpoint_vars = json.loads(record.endpoint_variables)
                    all_variables.update(endpoint_vars)
                except json.JSONDecodeError:
                    pass

            # Replace variables in URL path using {variable} format only
            if all_variables and url:
                for key, value in all_variables.items():
                    placeholder = f"{{{key}}}"
                    if placeholder in url:
                        url = url.replace(placeholder, str(value))

            record.full_url = url

    @api.onchange('use_collection_url', 'collection_id')
    def _onchange_use_collection_url(self):
        """Update base_url when toggling collection inheritance"""
        if self.use_collection_url and self.collection_id:
            self.base_url = self.collection_id.base_url
        elif not self.use_collection_url:
            # Clear the field when unchecking to allow manual input
            self.base_url = ''

    @api.depends('total_calls', 'success_calls')
    def _compute_success_rate(self):
        """Compute success rate as decimal (widget percentage will multiply by 100)"""
        for record in self:
            if record.total_calls > 0 and record.success_calls <= record.total_calls:
                record.success_rate = record.success_calls / record.total_calls
            else:
                record.success_rate = 0.0

    @api.constrains('base_url')
    def _check_base_url(self):
        """Validate base URL format"""
        for record in self:
            if record.base_url and not record.base_url.startswith(('http://', 'https://')):
                raise ValidationError(_("Base URL must start with http:// or https://"))

    @api.constrains('custom_headers')
    def _check_custom_headers(self):
        """Validate custom headers JSON format"""
        for record in self:
            if record.custom_headers:
                try:
                    json.loads(record.custom_headers)
                except json.JSONDecodeError:
                    raise ValidationError(_("Custom headers must be valid JSON format"))

    @api.constrains('timeout')
    def _check_timeout(self):
        """Validate timeout value"""
        for record in self:
            if record.timeout <= 0 or record.timeout > 300:
                raise ValidationError(_("Timeout must be between 1 and 300 seconds"))

    @api.constrains('endpoint_variables')
    def _check_endpoint_variables(self):
        """Validate endpoint variables JSON format"""
        for record in self:
            if record.endpoint_variables:
                try:
                    params = json.loads(record.endpoint_variables)
                    if not isinstance(params, dict):
                        raise ValidationError(_("Endpoint variables must be a JSON object (dictionary)"))
                except json.JSONDecodeError:
                    raise ValidationError(_("Endpoint variables must be valid JSON format"))

    def _prepare_headers(self):
        """Prepare request headers with collection inheritance"""
        headers = {}

        # Start with collection default headers if available
        if self.collection_id and self.collection_id.default_headers:
            try:
                collection_headers = json.loads(self.collection_id.default_headers)
                headers.update(collection_headers)
            except json.JSONDecodeError:
                _logger.warning(f"Invalid collection headers JSON for collection {self.collection_id.name}")

        # Override with endpoint-specific headers
        if self.custom_headers:
            try:
                custom = json.loads(self.custom_headers)
                headers.update(custom)
            except json.JSONDecodeError:
                _logger.warning(f"Invalid custom headers JSON for API {self.name}")

        # Determine authentication (endpoint overrides collection)
        auth_type = self.auth_type
        auth_token = self.auth_token
        auth_header_name = self.auth_header_name
        oauth_access_token = self.oauth_access_token

        # Inherit from collection if endpoint auth is 'inherit'
        if auth_type == 'inherit' and self.collection_id:
            auth_type = self.collection_id.auth_type
            auth_token = self.collection_id.auth_token
            auth_header_name = self.collection_id.auth_header_name

        # Add authentication headers
        if auth_type == 'bearer' and auth_token:
            headers['Authorization'] = f'Bearer {auth_token}'
        elif auth_type == 'oauth2':
            # Use OAuth access token if available, otherwise use manual token
            token = oauth_access_token or auth_token
            if token:
                headers['Authorization'] = f'Bearer {token}'
        elif auth_type == 'api_key' and auth_token:
            headers[auth_header_name or 'X-API-Key'] = auth_token

        # Set default content type if not specified
        if self.request_body_type == 'json' and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/json'
        elif self.request_body_type == 'xml' and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/xml'
        elif self.request_body_type == 'form' and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        elif self.request_body_type == 'form_multipart' and 'Content-Type' not in headers:
            headers['Content-Type'] = 'multipart/form-data'
        elif self.request_body_type == 'binary' and 'Content-Type' not in headers:
            headers['Content-Type'] = 'application/octet-stream'

        return headers

    def _prepare_auth(self):
        """Prepare authentication for requests with collection inheritance"""
        # Determine auth values (endpoint overrides collection)
        auth_type = self.auth_type
        auth_username = self.auth_username
        auth_password = self.auth_password

        # Inherit from collection if endpoint auth is 'inherit'
        if auth_type == 'inherit' and self.collection_id:
            auth_type = self.collection_id.auth_type
            auth_username = self.collection_id.auth_username
            auth_password = self.collection_id.auth_password

        if auth_type == 'basic' and auth_username and auth_password:
            return (auth_username, auth_password)
        return None

    def _prepare_body(self, dynamic_data=None):
        """Prepare request body with dynamic data substitution"""
        if self.request_body_type == 'none':
            return None

        # Handle form data from dedicated field
        if self.request_body_type in ['form', 'form_multipart'] and self.form_data:
            try:
                form_dict = json.loads(self.form_data)
                # Replace dynamic variables in form data
                if dynamic_data:
                    for key, value in dynamic_data.items():
                        for form_key, form_value in form_dict.items():
                            placeholder = f"{{{key}}}"
                            if placeholder in str(form_value):
                                form_dict[form_key] = str(form_value).replace(placeholder, str(value))
                return form_dict
            except json.JSONDecodeError as e:
                raise UserError(_("Invalid JSON in form data: %s") % str(e))

        # Handle other body types
        if not self.request_body:
            return None

        body = self.request_body

        # Replace dynamic variables if provided
        if dynamic_data:
            for key, value in dynamic_data.items():
                placeholder = f"{{{key}}}"
                if placeholder in body:
                    body = body.replace(placeholder, str(value))

        # Process by type
        if self.request_body_type == 'json':
            try:
                return json.loads(body)
            except json.JSONDecodeError as e:
                raise UserError(_("Invalid JSON in request body: %s") % str(e))
        elif self.request_body_type == 'binary':
            try:
                # Decode base64 for binary data
                return base64.b64decode(body)
            except Exception as e:
                raise UserError(_("Invalid base64 in binary body: %s") % str(e))

        return body

    def execute_call(self, dynamic_data=None):
        """Execute the API call"""
        self.ensure_one()

        if not self.active:
            raise UserError(_("API connection '%s' is not active") % self.name)

        # Clear previous response data
        self.write({
            'last_response_success': False,
            'last_response_status': 0,
            'last_response_time': 0,
            'last_response_data': None,
            'last_response_error': None,
        })

        start_time = datetime.now()

        try:
            # Prepare request components
            headers = self._prepare_headers()
            auth = self._prepare_auth()
            body = self._prepare_body(dynamic_data)

            # Make the request with appropriate body handling
            request_kwargs = {
                'method': self.method,
                'url': self.full_url,
                'headers': headers,
                'auth': auth,
                'timeout': self.timeout,
                'verify': self.verify_ssl
            }

            # Handle different body types
            if self.request_body_type == 'json':
                request_kwargs['json'] = body
            elif self.request_body_type == 'form':
                request_kwargs['data'] = body
            elif self.request_body_type == 'form_multipart':
                # For multipart, let requests handle the Content-Type
                if 'Content-Type' in headers and 'multipart' in headers['Content-Type']:
                    del headers['Content-Type']
                request_kwargs['data'] = body
            elif self.request_body_type == 'binary':
                request_kwargs['data'] = body
            elif self.request_body_type in ['xml', 'raw']:
                request_kwargs['data'] = body

            response = requests.request(**request_kwargs)

            # Calculate execution time
            execution_time = (datetime.now() - start_time).total_seconds()

            # Process response
            response_data = self._process_response(response)
            _logger.info(
                f"API call to {self.full_url} - Status: {response.status_code}, Response size: {len(str(response_data))}")

            # Log the call
            self._log_api_call(
                success=response.ok,
                status_code=response.status_code,
                request_data=dynamic_data,
                response_data=response_data,
                execution_time=execution_time,
                error_message=None if response.ok else f"HTTP {response.status_code}: {response.reason}"
            )

            # Update statistics
            self._update_statistics(success=response.ok)

            # Store response for display in UI
            _logger.info(
                f"Storing response data: success={response.ok}, status={response.status_code}, data_type={type(response_data)}")
            self._store_last_response(
                success=response.ok,
                status_code=response.status_code,
                data=response_data,
                execution_time=execution_time,
                error_message=None if response.ok else f"HTTP {response.status_code}: {response.reason}"
            )

            # Les champs sont mis à jour automatiquement par self.write()
            # L'interface Odoo se rafraîchit automatiquement
            return True

        except requests.exceptions.Timeout:
            error_msg = _("Request timeout after %d seconds") % self.timeout
            self._log_api_call(success=False, error_message=error_msg)
            self._update_statistics(success=False)
            self._store_last_response(success=False, error_message=error_msg)
            return True

        except requests.exceptions.ConnectionError:
            error_msg = _("Connection error: Unable to connect to %s") % self.full_url
            self._log_api_call(success=False, error_message=error_msg)
            self._update_statistics(success=False)
            self._store_last_response(success=False, error_message=error_msg)
            return True

        except Exception as e:
            error_msg = str(e)
            self._log_api_call(success=False, error_message=error_msg)
            self._update_statistics(success=False)
            self._store_last_response(success=False, error_message=error_msg)
            return True

    def _process_response(self, response):
        """Process the API response based on expected type"""
        try:
            if self.expected_response_type == 'json':
                return response.json()
            elif self.expected_response_type == 'xml':
                return response.text
            elif self.expected_response_type == 'binary':
                return base64.b64encode(response.content).decode('utf-8')
            else:  # text
                return response.text
        except Exception as e:
            _logger.warning(f"Error processing response for API {self.name}: {e}")
            return response.text

    def _log_api_call(self, success=True, status_code=None, request_data=None,
                      response_data=None, execution_time=None, error_message=None):
        """Log the API call"""
        try:
            self.env['api.call.log'].create({
                'connector_id': self.id,
                'success': success,
                'status_code': status_code,
                'request_data': json.dumps(request_data) if request_data else None,
                'response_data': json.dumps(response_data, ensure_ascii=False) if isinstance(response_data, (dict, list)) else str(response_data),
                'execution_time': execution_time,
                'error_message': error_message,
                'call_date': fields.Datetime.now()
            })
        except Exception as e:
            _logger.error(f"Failed to log API call for {self.name}: {e}")

    def _update_statistics(self, success=True):
        """Update call statistics"""
        # Use write() instead of += to avoid concurrency issues
        new_total = self.total_calls + 1
        new_success = self.success_calls + (1 if success else 0)

        self.write({
            'total_calls': new_total,
            'success_calls': new_success,
            'last_call_date': fields.Datetime.now()
        })

    def _store_last_response(self, success=True, status_code=None, data=None,
                             execution_time=None, error_message=None):
        """Store the last API response for display in UI"""
        try:
            _logger.info(f"_store_last_response called: success={success}, status={status_code}, data={type(data)}")

            # Format response data
            if data is not None:
                if isinstance(data, (dict, list)):
                    response_data = json.dumps(data, indent=2, ensure_ascii=False)
                    _logger.info(f"Formatted JSON data: {len(response_data)} characters")
                else:
                    response_data = str(data)
                    _logger.info(f"Formatted string data: {len(response_data)} characters")
            else:
                response_data = None
                _logger.info("No response data to store")

            # Update fields
            update_vals = {
                'last_response_success': success,
                'last_response_status': status_code or 0,
                'last_response_time': (execution_time * 1000) if execution_time else 0,
                'last_response_data': response_data,
                'last_response_error': error_message,
            }
            _logger.info(f"Writing update_vals: {update_vals}")
            self.write(update_vals)
            _logger.info(f"Response stored successfully for {self.name}")
        except Exception as e:
            _logger.error(f"Failed to store last response for {self.name}: {e}")

    @api.model
    def create_rest_template(self, name, base_url, endpoint_path=''):
        """Helper method to create a REST API template"""
        return self.create({
            'name': name,
            'base_url': base_url,
            'endpoint_path': endpoint_path,
            'api_type': 'rest',
            'method': 'GET',
            'auth_type': 'none',
            'request_body_type': 'none',
            'expected_response_type': 'json'
        })

    def action_view_collection(self):
        """Open the collection this endpoint belongs to"""
        self.ensure_one()
        if not self.collection_id:
            raise UserError(_("This endpoint is not part of any collection"))

        return {
            'type': 'ir.actions.act_window',
            'name': _('Collection: %s') % self.collection_id.name,
            'res_model': 'api.collection',
            'res_id': self.collection_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.model
    def fix_success_rates(self):
        connectors = self.search([('success_rate', '>', 1.0)])
        for connector in connectors:
            if connector.total_calls > 0:
                # Recalculate correctly
                new_rate = connector.success_calls / connector.total_calls
                connector.write({'success_rate': new_rate})
                _logger.info(
                    f"Fixed success rate for {connector.name}: {connector.success_rate * 100:.1f}% -> {new_rate * 100:.1f}%")
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

                    # Update connector with new tokens
                    self.write({
                        'oauth_access_token': access_token,
                        'oauth_refresh_token': refresh_token,
                        'oauth_token_expires_at': expires_at,
                    })

                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('OAuth Token Retrieved Successfully'),
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
                        'title': _('OAuth Token Request Failed'),
                        'message': f'Status: {response.status_code} | Error: {error_detail}',
                        'type': 'danger',
                        'sticky': True,
                    }
                }

        except requests.exceptions.RequestException as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('OAuth Request Error'),
                    'message': f'Connection Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('OAuth Error'),
                    'message': f'Error: {str(e)}',
                    'type': 'danger',
                    'sticky': True,
                }
            }

    def export_config(self):
        """Export connector configuration to JSON"""
        self.ensure_one()

        # Fields to export (excluding computed, related, and system fields)
        export_fields = [
            'name', 'active', 'api_type', 'method', 'base_url', 'endpoint_path',
            'endpoint_variables', 'auth_type', 'auth_username',
            'auth_password', 'auth_token', 'oauth_client_id', 'oauth_client_secret',
            'oauth_authorization_url', 'oauth_token_url', 'oauth_scope',
            'auth_header_name', 'custom_headers', 'request_body_type',
            'request_body', 'form_data', 'file_field_name', 'expected_response_type',
            'timeout', 'verify_ssl', 'use_collection_url'
        ]

        config = {}
        for field in export_fields:
            if hasattr(self, field):
                value = getattr(self, field)
                if value:  # Only export non-empty values
                    config[field] = value

        # Add collection info if linked
        if self.collection_id:
            config['collection_name'] = self.collection_id.name

        # Add metadata
        config['_metadata'] = {
            'export_date': fields.Datetime.now().isoformat(),
            'export_user': self.env.user.name,
            'odoo_version': '18.0',
            'module_version': '1.0.0',
            'type': 'api_connector'
        }

        # Create attachment with JSON content
        json_content = json.dumps(config, indent=2, ensure_ascii=False)
        attachment = self.env['ir.attachment'].create({
            'name': f'api_connector_{self.name}_{fields.Date.today()}.json',
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
    def import_config(self, json_data, collection_id=None):
        """Import connector configuration from JSON"""
        try:
            if isinstance(json_data, str):
                config = json.loads(json_data)
            else:
                config = json_data
        except json.JSONDecodeError as e:
            raise UserError(_("Invalid JSON format: %s") % str(e))

        # Validate metadata
        if '_metadata' not in config or config['_metadata'].get('type') != 'api_connector':
            raise UserError(_("Invalid configuration file: not an API connector export"))

        # Remove metadata for import
        metadata = config.pop('_metadata', {})
        collection_name = config.pop('collection_name', None)

        # Find or create collection if specified
        if collection_id:
            collection = self.env['api.collection'].browse(collection_id)
            if not collection.exists():
                collection_id = None
        elif collection_name:
            collection = self.env['api.collection'].search([('name', '=', collection_name)], limit=1)
            if collection:
                collection_id = collection.id
            else:
                collection_id = None

        # Set collection_id in config
        if collection_id:
            config['collection_id'] = collection_id

        # Validate required fields
        if 'name' not in config:
            raise UserError(_("Configuration must contain a 'name' field"))

        # Create the connector
        connector = self.create(config)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Imported Connector: %s') % connector.name,
            'res_model': 'api.connector',
            'res_id': connector.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def unlink(self):
        """Override unlink to protect system critical routes"""
        critical_routes = self.filtered('is_system_critical')
        if critical_routes:
            # Check if user has confirmed deletion of critical routes
            if not self.env.context.get('force_delete_critical'):
                raise UserError(_(
                    'Cannot delete system critical routes: %s\n\n'
                    'These routes are essential for system operation. '
                    'If you need to disable them, use the "Active" toggle instead. '
                    'Contact your system administrator if deletion is really necessary.'
                ) % ', '.join(critical_routes.mapped('name')))

        return super().unlink()
