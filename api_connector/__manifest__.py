{
    'name': 'API Connector - Outbound REST & JSON-RPC',
    'summary': '🚀 Postman-like interface for configuring outbound API calls from Odoo',
    'price': 199.00,
    'currency': 'EUR',
    'description': '''
🚀 **API CONNECTOR - OUTBOUND API CALLS FROM ODOO**

The perfect companion to json_rpc_api module! While json_rpc_api handles INBOUND calls to Odoo,
API Connector manages OUTBOUND calls from Odoo to external APIs.

## ✨ **KEY FEATURES**

### 🎯 **Postman-like Interface**
- Visual configuration of API calls (no coding required)
- Support for REST, JSON-RPC, GraphQL, SOAP
- Real-time testing directly in Odoo
- Request/Response history and logging

### 🔧 **Flexible Configuration**
- Multiple HTTP methods (GET, POST, PUT, DELETE, PATCH)
- Custom headers and authentication
- Dynamic data mapping from Odoo records
- Environment variables (dev/staging/prod)

### 🛡️ **Enterprise Security**
- Secure credential storage
- OAuth 2.0, API Key, Basic Auth support
- SSL/TLS verification
- Rate limiting and timeout controls

### 📊 **Monitoring & Analytics**
- Complete request/response logging
- Success/failure statistics
- Performance metrics
- Error tracking and alerts

## 🎮 **USE CASES**

### **E-commerce Integration**
- Sync products to external marketplaces
- Update inventory levels in real-time
- Process payment callbacks
- Send order confirmations

### **CRM Integration**
- Push leads to external systems
- Sync customer data with marketing tools
- Trigger email campaigns
- Update contact information

### **Accounting Integration**
- Export invoices to accounting software
- Sync payment status
- Generate financial reports
- Tax compliance reporting

## 🏗️ **ARCHITECTURE**

### **Phase 1 - Core Module**
- REST API support (GET/POST/PUT/DELETE)
- Basic authentication methods
- Request/response logging
- Postman-like interface

### **Phase 2 - Protocol Extensions**
- JSON-RPC support (complement to json_rpc_api)
- GraphQL queries and mutations
- SOAP/XML web services
- Custom protocol adapters

### **Phase 3 - Service Extensions**
- Pre-built connectors for popular APIs
- Template library for common integrations
- Workflow automation
- Advanced error handling

## 🚀 **GETTING STARTED**

1. Install the module
2. Go to API Connector → Outbound APIs
3. Create new API connection using Postman-like interface
4. Test the connection
5. Configure triggers (manual, cron, or event-based)

**Transform Odoo into a powerful integration hub!**

---
**🇫🇷 Developed by IROKOO | Premium French Quality**
    ''',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'license': 'OPL-1',
    'author': 'IROKOO | Chti-tech | Sylvain Boutet',
    'website': 'https://www.irokoo.fr',
    'maintainer': 'Sylvain Boutet <sbt@irokoo.fr>',
    'support': 'sbt@irokoo.fr',
    'depends': [
        'base',
        'web',
    ],
    'external_dependencies': {
        'python': ['requests', 'jsonschema']
    },
    'data': [
        'security/api_connector_security.xml',
        'security/ir.model.access.csv',
        'data/api_connector_data.xml',
        'data/preconfigured_routes.xml',
        'wizard/import_config_wizard_views.xml',
        'views/api_collection_views.xml',
        'views/api_connector_views.xml',
        'views/api_call_log_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
        ],
    },
    'images': [
        'static/description/icon.png',
    ],
    'application': True,
    'installable': True,
    'auto_install': False,
}
