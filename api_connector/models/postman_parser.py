# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import json
import re
from urllib.parse import urlparse, parse_qs


class PostmanParser(models.AbstractModel):
    """Parser for Postman collections to API Connector format"""
    _name = 'postman.parser'
    _description = 'Postman Collection Parser'

    @api.model
    def parse_collection(self, postman_data):
        """
        Parse Postman collection and convert to API Connector format

        Args:
            postman_data (dict): Postman collection JSON data

        Returns:
            dict: Parsed data in API Connector format
        """
        if isinstance(postman_data, str):
            try:
                postman_data = json.loads(postman_data)
            except json.JSONDecodeError as e:
                raise UserError(_("Invalid JSON format: %s") % str(e))

        # Validate Postman format
        if 'info' not in postman_data:
            raise UserError(_("Invalid Postman collection: missing 'info' section"))

        info = postman_data.get('info', {})
        collection_name = info.get('name', 'Imported Collection')
        collection_description = info.get('description', 'Imported from Postman')

        # Extract collection-level variables and auth
        collection_auth = postman_data.get('auth', {})
        collection_variables = self._extract_variables(postman_data.get('variable', []))

        # Parse items (folders and requests)
        connectors = []
        if 'item' in postman_data:
            connectors = self._parse_items(postman_data['item'])

        # Build collection configuration
        collection_config = {
            'name': collection_name,
            'description': collection_description,
            'auth_type': self._convert_auth_type(collection_auth),
            'collection_variables': json.dumps(collection_variables) if collection_variables else None,
            'connectors': connectors,
            '_metadata': {
                'type': 'api_collection',
                'source': 'postman_import',
                'original_format': 'postman_v2.1',
                'import_date': fields.Datetime.now().isoformat(),
                'connectors_count': len(connectors)
            }
        }

        # Extract base URL from first request if available
        base_url = self._extract_base_url(connectors)
        if base_url:
            collection_config['base_url'] = base_url

        # Extract auth details
        auth_details = self._extract_auth_details(collection_auth)
        collection_config.update(auth_details)

        return collection_config

    def _parse_items(self, items, folder_path=""):
        """Recursively parse Postman items (folders and requests)"""
        connectors = []

        for item in items:
            if 'item' in item:  # Folder
                folder_name = item.get('name', 'Unknown Folder')
                new_path = f"{folder_path}/{folder_name}" if folder_path else folder_name
                connectors.extend(self._parse_items(item['item'], new_path))
            else:  # Request
                connector = self._parse_request(item, folder_path)
                if connector:
                    connectors.append(connector)

        return connectors

    def _parse_request(self, request_item, folder_path=""):
        """Parse individual Postman request"""
        name = request_item.get('name', 'Unknown Request')
        if folder_path:
            name = f"{folder_path} - {name}"

        request = request_item.get('request', {})
        if not isinstance(request, dict):
            return None

        # Extract method
        method = request.get('method', 'GET').upper()

        # Extract URL
        url_info = request.get('url', {})
        if isinstance(url_info, str):
            url_info = {'raw': url_info}

        raw_url = url_info.get('raw', '')

        # Parse URL components
        endpoint_path, variables, base_url = self._parse_url(url_info)

        # Extract headers
        headers = self._extract_headers(request.get('header', []))

        # Extract body
        body_info = self._extract_body(request.get('body', {}))

        # Extract auth (request-level overrides collection-level)
        auth = request.get('auth', {})
        auth_details = self._extract_auth_details(auth)

        # Build connector configuration
        connector_config = {
            'name': name,
            'api_type': 'rest',  # Default to REST, could be enhanced
            'method': method,
            'endpoint_path': endpoint_path,
            'use_collection_url': bool(base_url),  # Use collection URL if we extracted a base
            'active': True
        }

        # Add variables if present
        if variables:
            connector_config['endpoint_variables'] = json.dumps(variables)

        # Add custom headers
        if headers:
            connector_config['custom_headers'] = json.dumps(headers)

        # Add body information
        if body_info['type']:
            connector_config['request_body_type'] = body_info['type']
        if body_info['content']:
            connector_config['request_body'] = body_info['content']

        # Add auth details (if different from collection)
        if auth_details:
            connector_config.update(auth_details)

        # Add base URL if not using collection URL
        if not connector_config['use_collection_url'] and base_url:
            connector_config['base_url'] = base_url

        return connector_config

    def _parse_url(self, url_info):
        """Parse Postman URL structure"""
        raw_url = url_info.get('raw', '')

        # Extract path parts
        path_parts = url_info.get('path', [])
        if path_parts:
            endpoint_path = '/' + '/'.join(str(p) for p in path_parts)
        else:
            # Fallback: extract path from raw URL
            parsed = urlparse(raw_url)
            endpoint_path = parsed.path or '/'

        # Extract query parameters as variables
        query_params = url_info.get('query', [])
        variables = {}

        for param in query_params:
            if isinstance(param, dict):
                key = param.get('key', '')
                value = param.get('value', '')
                if key:
                    variables[key] = value

        # Extract base URL (protocol + host + port)
        base_url = None
        if raw_url:
            parsed = urlparse(raw_url)
            if parsed.netloc:
                base_url = f"{parsed.scheme}://{parsed.netloc}"

        # Convert Postman variables {{var}} to API Connector format {var}
        endpoint_path = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', endpoint_path)

        # Extract variables from path
        path_variables = re.findall(r'\{([^}]+)\}', endpoint_path)
        for var in path_variables:
            if var not in variables:
                variables[var] = f"{{var_{var}}}"  # Placeholder value

        return endpoint_path, variables, base_url

    def _extract_variables(self, postman_variables):
        """Extract Postman collection variables"""
        variables = {}

        for var in postman_variables:
            if isinstance(var, dict):
                key = var.get('key', '')
                value = var.get('value', var.get('initial', ''))
                if key:
                    variables[key] = value

        return variables

    def _extract_headers(self, postman_headers):
        """Extract headers from Postman request"""
        headers = {}

        for header in postman_headers:
            if isinstance(header, dict) and not header.get('disabled', False):
                key = header.get('key', '')
                value = header.get('value', '')
                if key and value:
                    # Convert Postman variables
                    value = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', value)
                    headers[key] = value

        return headers

    def _extract_body(self, postman_body):
        """Extract request body from Postman request"""
        if not postman_body:
            return {'type': None, 'content': None}

        mode = postman_body.get('mode', '')

        if mode == 'raw':
            content = postman_body.get('raw', '')
            # Try to detect if it's JSON
            try:
                json.loads(content)
                body_type = 'json'
            except BaseException:
                body_type = 'raw'

            # Convert Postman variables
            content = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', content)

            return {'type': body_type, 'content': content}

        elif mode == 'formdata':
            return {'type': 'form_data', 'content': None}

        elif mode == 'urlencoded':
            return {'type': 'form_urlencoded', 'content': None}

        elif mode == 'file':
            return {'type': 'binary', 'content': None}

        elif mode == 'graphql':
            graphql_data = postman_body.get('graphql', {})
            query = graphql_data.get('query', '')
            variables = graphql_data.get('variables', '{}')

            # Build GraphQL request body
            try:
                variables_obj = json.loads(variables) if variables else {}
                content = json.dumps({
                    'query': query,
                    'variables': variables_obj
                })
                return {'type': 'json', 'content': content}
            except BaseException:
                return {'type': 'json', 'content': json.dumps({'query': query})}

        return {'type': None, 'content': None}

    def _convert_auth_type(self, postman_auth):
        """Convert Postman auth type to API Connector format"""
        if not postman_auth:
            return 'none'

        auth_type = postman_auth.get('type', 'none')

        # Mapping Postman auth types to API Connector types
        auth_mapping = {
            'noauth': 'none',
            'basic': 'basic',
            'bearer': 'bearer',
            'apikey': 'api_key',
            'oauth2': 'oauth2',
            'digest': 'basic',  # Fallback to basic
            'hawk': 'api_key',  # Fallback to api_key
            'awsv4': 'api_key',  # Fallback to api_key
        }

        return auth_mapping.get(auth_type, 'none')

    def _extract_auth_details(self, postman_auth):
        """Extract authentication details from Postman auth object"""
        if not postman_auth:
            return {}

        auth_type = postman_auth.get('type', 'none')
        auth_data = postman_auth.get(auth_type, {})

        details = {}

        if auth_type == 'basic':
            details.update({
                'auth_type': 'basic',
                'auth_username': self._get_auth_value(auth_data, 'username'),
                'auth_password': self._get_auth_value(auth_data, 'password')
            })

        elif auth_type == 'bearer':
            details.update({
                'auth_type': 'bearer',
                'auth_token': self._get_auth_value(auth_data, 'token')
            })

        elif auth_type == 'apikey':
            key = self._get_auth_value(auth_data, 'key')
            value = self._get_auth_value(auth_data, 'value')
            in_header = self._get_auth_value(auth_data, 'in') == 'header'

            if in_header:
                details.update({
                    'auth_type': 'api_key',
                    'auth_header_name': key,
                    'auth_token': value
                })
            else:
                # Query parameter auth - could be enhanced
                details.update({
                    'auth_type': 'api_key',
                    'auth_header_name': key,
                    'auth_token': value
                })

        return details

    def _get_auth_value(self, auth_data, key):
        """Get auth value from Postman auth data structure"""
        if isinstance(auth_data, list):
            for item in auth_data:
                if isinstance(item, dict) and item.get('key') == key:
                    return item.get('value', '')
        elif isinstance(auth_data, dict):
            return auth_data.get(key, '')

        return ''

    def _extract_base_url(self, connectors):
        """Extract common base URL from connectors"""
        if not connectors:
            return None

        # Look for base_url in first connector
        first_connector = connectors[0]
        return first_connector.get('base_url')

    @api.model
    def validate_postman_collection(self, postman_data):
        """Validate if the data is a valid Postman collection"""
        try:
            if isinstance(postman_data, str):
                postman_data = json.loads(postman_data)

            # Check for required Postman collection structure
            if not isinstance(postman_data, dict):
                return False, _("Data must be a JSON object")

            if 'info' not in postman_data:
                return False, _("Missing 'info' section - not a valid Postman collection")

            info = postman_data['info']
            if not isinstance(info, dict) or 'name' not in info:
                return False, _("Invalid 'info' section - missing collection name")

            # Check for schema and version compatibility
            schema = info.get('schema', '')
            if schema:
                if 'postman' not in schema.lower():
                    return False, _("Schema indicates this is not a Postman collection")

                # Check for supported versions
                supported_versions = ['v2.0', 'v2.1', 'v2.2']
                version_found = False

                for version in supported_versions:
                    if version in schema:
                        version_found = True
                        break

                if not version_found:
                    # Extract version from schema for better error message
                    version_match = re.search(r'v(\d+\.\d+)', schema)
                    detected_version = version_match.group(0) if version_match else 'unknown'

                    return False, _("Unsupported Postman collection version '%s'. Supported versions: %s") % (
                        detected_version, ', '.join(supported_versions)
                    )

            # Additional validation for required structure
            validation_result = self._validate_collection_structure(postman_data)
            if not validation_result[0]:
                return validation_result

            return True, _("Valid Postman collection")

        except json.JSONDecodeError as e:
            return False, _("Invalid JSON format: %s") % str(e)
        except Exception as e:
            return False, _("Validation error: %s") % str(e)

    @api.model
    def _validate_collection_structure(self, postman_data):
        """Validate the internal structure of Postman collection"""

        # Check if collection has items
        if 'item' not in postman_data:
            return False, _("Collection has no items (requests or folders)")

        items = postman_data['item']
        if not isinstance(items, list):
            return False, _("Collection items must be a list")

        if len(items) == 0:
            return False, _("Collection is empty - no requests found")

        # Validate at least one item structure
        validation_errors = []
        valid_items = 0

        for i, item in enumerate(items[:5]):  # Check first 5 items
            try:
                item_validation = self._validate_item_structure(item, f"Item {i+1}")
                if item_validation[0]:
                    valid_items += 1
                else:
                    validation_errors.append(item_validation[1])
            except Exception as e:
                validation_errors.append(f"Item {i+1}: {str(e)}")

        if valid_items == 0:
            error_summary = "; ".join(validation_errors[:3])  # Show first 3 errors
            return False, _("No valid requests found in collection. Errors: %s") % error_summary

        # Check for unsupported features
        unsupported_features = self._check_unsupported_features(postman_data)
        if unsupported_features:
            return False, _("Collection contains unsupported features: %s") % ", ".join(unsupported_features)

        return True, _("Collection structure is valid")

    @api.model
    def _validate_item_structure(self, item, item_name="Item"):
        """Validate individual item (request or folder) structure"""

        if not isinstance(item, dict):
            return False, f"{item_name}: Must be an object"

        # Check if it's a folder
        if 'item' in item:
            # It's a folder - validate recursively
            if not isinstance(item['item'], list):
                return False, f"{item_name}: Folder items must be a list"
            return True, f"{item_name}: Valid folder"

        # It's a request - validate request structure
        if 'request' not in item:
            return False, f"{item_name}: Missing 'request' field"

        request = item['request']

        # Handle string URLs (legacy format)
        if isinstance(request, str):
            return True, f"{item_name}: Valid request (legacy URL format)"

        if not isinstance(request, dict):
            return False, f"{item_name}: Request must be an object"

        # Validate required request fields
        if 'url' not in request and 'method' not in request:
            return False, f"{item_name}: Request missing both 'url' and 'method'"

        # Validate method
        method = request.get('method', 'GET')
        valid_methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']
        if method not in valid_methods:
            return False, f"{item_name}: Unsupported HTTP method '{method}'"

        return True, f"{item_name}: Valid request"

    @api.model
    def _check_unsupported_features(self, postman_data):
        """Check for Postman features that are not supported"""

        unsupported = []

        # Check for unsupported auth types
        auth = postman_data.get('auth', {})
        if auth:
            auth_type = auth.get('type', '')
            unsupported_auth_types = ['ntlm', 'hawk', 'awsv4', 'edgegrid']
            if auth_type in unsupported_auth_types:
                unsupported.append(f"Authentication type '{auth_type}'")

        # Check for pre-request scripts
        if 'event' in postman_data:
            events = postman_data['event']
            for event in events:
                if event.get('listen') == 'prerequest':
                    unsupported.append("Pre-request scripts")
                    break

        # Check for test scripts
        if 'event' in postman_data:
            events = postman_data['event']
            for event in events:
                if event.get('listen') == 'test':
                    unsupported.append("Test scripts")
                    break

        # Check items for unsupported features
        items = postman_data.get('item', [])
        for item in items:
            item_unsupported = self._check_item_unsupported_features(item)
            unsupported.extend(item_unsupported)

        return list(set(unsupported))  # Remove duplicates

    @api.model
    def _check_item_unsupported_features(self, item):
        """Check individual item for unsupported features"""

        unsupported = []

        # Check for item-level events
        if 'event' in item:
            unsupported.append("Item-level scripts")

        # If it's a folder, check recursively
        if 'item' in item:
            for sub_item in item['item']:
                unsupported.extend(self._check_item_unsupported_features(sub_item))

        # If it's a request, check request-specific features
        elif 'request' in item:
            request = item['request']
            if isinstance(request, dict):

                # Check for unsupported body types
                body = request.get('body', {})
                if body:
                    mode = body.get('mode', '')
                    unsupported_body_types = ['file', 'binary']
                    if mode in unsupported_body_types:
                        unsupported.append(f"Request body type '{mode}'")

                # Check for certificate authentication
                if 'certificate' in request:
                    unsupported.append("Certificate authentication")

                # Check for proxy settings
                if 'proxy' in request:
                    unsupported.append("Proxy settings")

        return unsupported
