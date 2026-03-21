import json
import base64
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ImportConfigWizard(models.TransientModel):
    _name = 'import.config.wizard'
    _description = 'Import API Configuration Wizard'

    state = fields.Selection([
        ('select', 'Select File'),
        ('preview', 'Preview'),
        ('done', 'Done')
    ], string='State', default='select')

    config_file = fields.Binary(
        string='Configuration File',
        required=True,
        help='Select a JSON configuration file to import'
    )
    filename = fields.Char(string='Filename')

    config_type = fields.Selection([
        ('auto', 'Auto-detect'),
        ('connector', 'API Connector'),
        ('collection', 'API Collection'),
        ('postman', 'Postman Collection')
    ], string='Configuration Type', default='auto', required=True)

    collection_id = fields.Many2one(
        'api.collection',
        string='Target Collection',
        help='Collection to import connector into (optional)'
    )

    preview_data = fields.Text(string='Preview', readonly=True)

    @api.onchange('config_file', 'filename')
    def _onchange_config_file(self):
        """Preview the configuration file content"""
        if self.config_file:
            try:
                # Decode the file
                file_content = base64.b64decode(self.config_file).decode('utf-8')
                config = json.loads(file_content)

                # Auto-detect type
                if '_metadata' in config:
                    config_type = config['_metadata'].get('type', 'unknown')
                    if config_type == 'api_connector':
                        self.config_type = 'connector'
                    elif config_type == 'api_collection':
                        self.config_type = 'collection'
                elif 'info' in config and isinstance(config['info'], dict):
                    # Postman collection detection with validation
                    parser = self.env['postman.parser']
                    is_valid, validation_message = parser.validate_postman_collection(config)

                    if is_valid:
                        self.config_type = 'postman'
                    else:
                        # Still detect as Postman but show validation issues in preview
                        info = config['info']
                        schema = info.get('schema', '')
                        if 'postman' in schema.lower() or 'name' in info:
                            self.config_type = 'postman'

                # Create preview based on detected type
                preview_lines = []

                if self.config_type == 'postman':
                    # Postman collection preview with validation
                    info = config.get('info', {})
                    preview_lines.append("Configuration Type: Postman Collection")
                    preview_lines.append(f"Name: {info.get('name', 'Unknown')}")

                    # Show schema/version info
                    schema = info.get('schema', '')
                    if schema:
                        version_match = re.search(r'v(\d+\.\d+)', schema)
                        version = version_match.group(0) if version_match else 'unknown'
                        preview_lines.append(f"Version: {version}")

                    # Validate collection and show status
                    parser = self.env['postman.parser']
                    is_valid, validation_message = parser.validate_postman_collection(config)

                    if is_valid:
                        preview_lines.append("✓ Status: Valid collection")

                        # Count requests
                        request_count = self._count_postman_requests(config.get('item', []))
                        preview_lines.append(f"Total Requests: {request_count}")

                        if 'variable' in config:
                            preview_lines.append(f"Variables: {len(config['variable'])}")

                        auth = config.get('auth', {})
                        if auth:
                            preview_lines.append(f"Authentication: {auth.get('type', 'Unknown')}")
                    else:
                        preview_lines.append("⚠ Status: Validation issues")
                        preview_lines.append(f"Issue: {validation_message}")

                        # Still show basic info
                        try:
                            request_count = self._count_postman_requests(config.get('item', []))
                            preview_lines.append(f"Detected Requests: {request_count}")
                        except BaseException:
                            preview_lines.append("Detected Requests: Unable to count")

                    preview_lines.append(f"Description: {info.get('description', 'No description')[:100]}...")

                else:
                    # Original API Connector format preview
                    preview_lines.append(f"Configuration Type: {config.get('_metadata', {}).get('type', 'Unknown')}")
                    preview_lines.append(f"Name: {config.get('name', 'Unknown')}")

                    if 'collection_name' in config:
                        preview_lines.append(f"Collection: {config['collection_name']}")

                    if 'connectors' in config:
                        preview_lines.append(f"Connectors: {len(config['connectors'])}")

                    if '_metadata' in config:
                        metadata = config['_metadata']
                        preview_lines.append(f"Export Date: {metadata.get('export_date', 'Unknown')}")
                        preview_lines.append(f"Export User: {metadata.get('export_user', 'Unknown')}")

                self.preview_data = '\n'.join(preview_lines)

            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                self.preview_data = f"Error reading file: {str(e)}"
        else:
            self.preview_data = ""

    def _count_postman_requests(self, items):
        """Count total requests in Postman collection"""
        count = 0
        for item in items:
            if 'item' in item:  # Folder
                count += self._count_postman_requests(item['item'])
            else:  # Request
                count += 1
        return count

    def action_import(self):
        """Import the configuration"""
        if not self.config_file:
            raise UserError(_("Please select a configuration file"))

        try:
            # Decode the file
            file_content = base64.b64decode(self.config_file).decode('utf-8')
            config = json.loads(file_content)

            # Determine import type
            if self.config_type == 'auto':
                if '_metadata' in config:
                    config_type = config['_metadata'].get('type')
                    if config_type == 'api_connector':
                        self.config_type = 'connector'
                    elif config_type == 'api_collection':
                        self.config_type = 'collection'
                    else:
                        raise UserError(_("Unknown configuration type: %s") % config_type)
                elif 'info' in config and isinstance(config['info'], dict):
                    # Auto-detect Postman collection
                    self.config_type = 'postman'
                else:
                    raise UserError(_("Cannot auto-detect configuration type. Please select manually."))

            # Import based on type
            if self.config_type == 'connector':
                return self.env['api.connector'].import_config(
                    config, self.collection_id.id if self.collection_id else None)
            elif self.config_type == 'collection':
                return self.env['api.collection'].import_config(config)
            elif self.config_type == 'postman':
                return self._import_postman_collection(config)
            else:
                raise UserError(_("Invalid configuration type"))

        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise UserError(_("Invalid file format: %s") % str(e))
        except Exception as e:
            raise UserError(_("Import failed: %s") % str(e))

    def _import_postman_collection(self, postman_data):
        """Import Postman collection using the parser"""
        try:
            # Validate collection first
            parser = self.env['postman.parser']
            is_valid, validation_message = parser.validate_postman_collection(postman_data)

            if not is_valid:
                raise UserError(_("Invalid Postman collection: %s") % validation_message)

            # Parse Postman collection
            collection_config = parser.parse_collection(postman_data)

            # Import as API collection
            result = self.env['api.collection'].import_config(collection_config)

            # Update success message
            if isinstance(result, dict) and result.get('type') == 'ir.actions.client':
                collection_name = collection_config.get('name', 'Unknown')
                connectors_count = len(collection_config.get('connectors', []))

                result.update({
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Postman Import Successful'),
                        'message': _('Collection "%s" imported with %d endpoints') % (collection_name, connectors_count),
                        'type': 'success',
                        'sticky': False,
                    }
                })

            return result

        except UserError:
            # Re-raise UserError as-is (already has good message)
            raise
        except Exception as e:
            # Wrap other exceptions with context
            raise UserError(_("Postman import failed: %s") % str(e))
