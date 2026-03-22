# API Connector - Outbound REST & JSON-RPC

A Postman-like API client integrated into Odoo for configuring and executing outbound API calls.

## 📋 Features

### ✅ Implemented
- **Collections & Connectors**: Organize endpoints with shared configuration
- **Multiple API Types**: REST, JSON-RPC, GraphQL, SOAP/XML support
- **Authentication Methods**: None, Basic Auth, Bearer Token, API Key, OAuth 2.0
- **Request Body Types**: JSON, XML, Form Data (URL-encoded & Multipart), Binary, Raw Text
- **File Upload**: Multipart form data with Odoo attachments
- **Dynamic Variables**: Hierarchical variable system (Collection → Endpoint → Dynamic)
- **URL Parameters**: Support for dynamic paths like `/api/orders/{order_id}`
- **Monitoring & Logs**: Detailed call history with success rates and response times
- **Cron Integration**: Execute API calls from scheduled actions
- **Inheritance Model**: Connectors can inherit settings from collections
- **Graphical Interface**: Postman-like UI with HTTP method ribbons and response display
- **Export/Import**: Backup and share configurations as JSON files
- **No-Code Server**: Create complete integrations using only Odoo's interface (crons + automated actions)

## 🚀 Installation

1. Copy the module to your Odoo addons directory
2. Update the module list
3. Install "API Connector - Outbound REST & JSON-RPC"

## 🔧 Configuration

### Collections
Create collections to group related endpoints:
- **Base URL**: Common API endpoint base
- **Authentication**: Shared auth configuration
- **Variables**: Reusable values across endpoints
- **Default Headers**: Common HTTP headers

### Connectors
Configure individual API endpoints:
- **HTTP Method**: GET, POST, PUT, PATCH, DELETE
- **Endpoint Path**: API path with optional parameters
- **Request Body**: JSON, XML, Form data, or file upload
- **Variables**: Endpoint-specific values

## 📖 Usage

### Manual Execution
1. Open an API Connector
2. Click "Execute Call"
3. View response in the Response tab

### Cron Jobs
Use connectors in scheduled actions:

```python
# Simple execution
connector = env['api.connector'].browse(123)
result = connector.execute_call()

# With dynamic variables
result = connector.execute_call({
    'order_id': record.id,
    'date': datetime.date.today().strftime('%Y-%m-%d'),
    'user_name': env.user.name
})
```

### File Upload
1. Set request body type to "Form Data (Multipart)"
2. Configure file field name (default: "ufile")
3. Select Odoo attachments to upload
4. Execute the call

### Export/Import Configurations
1. **Export**: Click "Export Config" button in connector/collection forms
2. **Import**: Use Configuration → Import Configuration menu
3. **Backup**: Save JSON files for configuration backup
4. **Share**: Distribute ready-to-use configurations
5. **Postman Import**: Import Postman collections directly (NEW!)

### No-Code Server Integrations
1. **Configure API**: Set up connector via graphical interface
2. **Schedule Calls**: Create cron job with minimal code
3. **Process Responses**: Use automated actions to handle API responses
4. **Complete Integration**: Full data sync without custom Python files

## 🧪 Testing

Run tests with:
```bash
odoo-bin --test-tags /api_connector --test-enable
```

## 📚 Documentation

- **French**: `documentation_api_connector.adoc`
- **English**: `documentation_api_connector_en.adoc`
- **In-app**: Documentation tabs in connector and collection forms

## 🐛 Known Issues

None currently reported.

## 🔄 Postman Import (NEW!)

### Import Postman Collections
The API Connector now supports importing Postman collections directly:

1. **Go to**: Configuration → Import Configuration
2. **Select**: Postman Collection JSON file
3. **Auto-detection**: The system automatically detects Postman format
4. **Import**: Creates collection + all endpoints automatically

### Supported Postman Features
- ✅ **Collections & Folders**: Organized endpoint structure
- ✅ **Authentication**: Bearer, Basic, API Key, OAuth 2.0
- ✅ **Variables**: Collection and request-level variables
- ✅ **Request Bodies**: JSON, Form data, GraphQL, Raw text
- ✅ **Headers**: Custom headers with variable substitution
- ✅ **URL Parameters**: Query parameters and path variables
- ✅ **Nested Folders**: Maintains folder organization in names

### Example Usage
```bash
# 1. Export from Postman
# File → Export → Collection v2.1 → Save as JSON

# 2. Import to Odoo
# API Connector → Configuration → Import Configuration
# Select your exported JSON file → Import
```

### Variable Conversion
Postman variables `{{variable}}` are automatically converted to API Connector format `{variable}`:

**Postman**: `https://{{base_url}}/api/{{version}}/users/{{user_id}}`  
**API Connector**: `https://{base_url}/api/{version}/users/{user_id}`

### Format Validation & Error Handling
The import wizard now includes comprehensive validation:

- ✅ **Version Check**: Supports Postman v2.0, v2.1, v2.2
- ✅ **Feature Detection**: Identifies unsupported features (scripts, advanced auth)
- ✅ **Structure Validation**: Ensures valid collection format
- ✅ **Detailed Errors**: Specific error messages for troubleshooting

**Example Error Messages**:
```
Unsupported Postman collection version 'v3.0'. Supported versions: v2.0, v2.1, v2.2
Collection contains unsupported features: Pre-request scripts, Authentication type 'ntlm'
No valid requests found in collection. Errors: Item 1: Missing 'request' field
```

See `static/description/POSTMAN_COMPATIBILITY.md` for complete compatibility details.

## 📈 Changelog

### v1.1.0 - 2025-01-03
- 🆕 **Postman Import**: Direct import of Postman collections
- 🆕 **Auto-detection**: Automatic format detection (Postman vs API Connector)
- 🆕 **Variable Conversion**: Automatic Postman → API Connector variable mapping
- 🆕 **Comprehensive Parser**: Support for all Postman features
- ✅ **Tests**: Complete test coverage for Postman import functionality

### v1.0.0 - 2025-01-03
- ✅ Initial release
- ✅ Collections and connectors implementation
- ✅ Multiple authentication methods
- ✅ File upload support
- ✅ Dynamic variables system
- ✅ Monitoring and logging
- ✅ Cron integration
- ✅ Export/Import configurations (JSON)
- ✅ Comprehensive documentation (French + English)

## 🤝 Contributing

This module follows Odoo development standards and best practices.

## 📄 License

LGPL-3

## 👨‍💻 Author

**Sylvain Boutet** - IROKOO  
Email: sylvain@irokoo.fr

---

**Compatible with Odoo 18.0**
