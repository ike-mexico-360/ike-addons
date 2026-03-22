# Postman Import - Compatibility Guide

## Supported Formats

### ✅ **Postman Collection Versions**
- **v2.0** - Basic collection format
- **v2.1** - Standard format (recommended)
- **v2.2** - Latest stable format

### ✅ **Supported Features**

#### **Collection Structure**
- ✅ Collections with folders and sub-folders
- ✅ Request organization and naming
- ✅ Collection-level variables
- ✅ Collection-level authentication
- ✅ Collection descriptions and metadata

#### **Authentication Methods**
- ✅ **None** - No authentication
- ✅ **Basic Auth** - Username/password
- ✅ **Bearer Token** - Token-based auth
- ✅ **API Key** - Header or query parameter
- ✅ **OAuth 2.0** - OAuth token (basic support)

#### **HTTP Methods**
- ✅ **GET** - Data retrieval
- ✅ **POST** - Data creation
- ✅ **PUT** - Data update (full)
- ✅ **PATCH** - Data update (partial)
- ✅ **DELETE** - Data deletion
- ✅ **HEAD** - Headers only
- ✅ **OPTIONS** - CORS preflight

#### **Request Body Types**
- ✅ **JSON** - Application/json content
- ✅ **Raw Text** - Plain text content
- ✅ **Form Data (URL-encoded)** - Application/x-www-form-urlencoded
- ✅ **Form Data (Multipart)** - Multipart/form-data
- ✅ **GraphQL** - GraphQL queries and mutations
- ✅ **XML** - XML content

#### **URL Features**
- ✅ **Dynamic URLs** - Variable substitution `{{variable}}`
- ✅ **Query Parameters** - URL query strings
- ✅ **Path Variables** - Dynamic path segments
- ✅ **Base URL inheritance** - Collection-level base URLs

#### **Headers**
- ✅ **Custom Headers** - User-defined headers
- ✅ **Dynamic Headers** - Variable substitution in headers
- ✅ **Authentication Headers** - Auto-generated auth headers

#### **Variables**
- ✅ **Collection Variables** - Shared across all requests
- ✅ **Request Variables** - Request-specific variables
- ✅ **Variable Substitution** - `{{variable}}` → `{variable}` conversion

## ❌ **Unsupported Features**

### **Authentication Methods**
- ❌ **NTLM** - Windows authentication
- ❌ **Hawk** - Hawk authentication protocol
- ❌ **AWS Signature v4** - AWS-specific auth
- ❌ **EdgeGrid** - Akamai EdgeGrid auth

### **Advanced Features**
- ❌ **Pre-request Scripts** - JavaScript code execution
- ❌ **Test Scripts** - Post-request JavaScript tests
- ❌ **Dynamic Variables** - `{{$randomInt}}`, `{{$timestamp}}`
- ❌ **Environments** - Postman environment switching
- ❌ **Data Files** - CSV/JSON data iteration

### **Request Body Types**
- ❌ **File Upload** - Binary file uploads
- ❌ **Binary Data** - Raw binary content

### **Advanced Settings**
- ❌ **Certificate Authentication** - Client certificates
- ❌ **Proxy Settings** - HTTP proxy configuration
- ❌ **SSL Settings** - Custom SSL/TLS settings
- ❌ **Timeout Settings** - Custom timeout values

## 🔄 **Conversion Process**

### **Variable Conversion**
Postman variables are automatically converted to API Connector format:

| Postman Format | API Connector Format | Status |
|----------------|---------------------|---------|
| `{{variable}}` | `{variable}` | ✅ Converted |
| `{{$randomInt}}` | Not converted | ❌ Unsupported |
| `{{$timestamp}}` | Not converted | ❌ Unsupported |

### **Authentication Conversion**
| Postman Auth | API Connector Auth | Status |
|--------------|-------------------|---------|
| No Auth | `none` | ✅ Supported |
| Basic Auth | `basic` | ✅ Supported |
| Bearer Token | `bearer` | ✅ Supported |
| API Key | `api_key` | ✅ Supported |
| OAuth 2.0 | `oauth2` | ✅ Basic support |
| NTLM | Not supported | ❌ Unsupported |

### **Body Type Conversion**
| Postman Body | API Connector Body | Status |
|--------------|-------------------|---------|
| raw (JSON) | `json` | ✅ Supported |
| raw (Text) | `raw` | ✅ Supported |
| form-data | `form_data` | ✅ Supported |
| x-www-form-urlencoded | `form_urlencoded` | ✅ Supported |
| GraphQL | `json` (converted) | ✅ Supported |
| binary | Not supported | ❌ Unsupported |

## 🚨 **Error Messages**

### **Version Errors**
```
Unsupported Postman collection version 'v3.0'. 
Supported versions: v2.0, v2.1, v2.2
```

### **Structure Errors**
```
Collection has no items (requests or folders)
```

```
No valid requests found in collection. 
Errors: Item 1: Missing 'request' field; Item 2: Invalid HTTP method
```

### **Feature Errors**
```
Collection contains unsupported features: 
Pre-request scripts, Authentication type 'ntlm'
```

### **Format Errors**
```
Missing 'info' section - not a valid Postman collection
```

## 💡 **Best Practices**

### **For Successful Import**
1. **Use Standard Versions**: Stick to v2.1 collections
2. **Avoid Scripts**: Remove pre-request and test scripts
3. **Simplify Auth**: Use basic auth methods (Bearer, API Key)
4. **Test Variables**: Ensure all variables have default values
5. **Clean Structure**: Organize requests in logical folders

### **Before Import**
1. **Export from Postman**: Use Collection v2.1 format
2. **Review Collection**: Check for unsupported features
3. **Test in Postman**: Ensure collection works in Postman
4. **Backup Original**: Keep original Postman collection

### **After Import**
1. **Review Variables**: Update variable values for your environment
2. **Test Endpoints**: Verify imported requests work correctly
3. **Update Authentication**: Configure proper credentials
4. **Organize Collection**: Adjust folder structure if needed

## 🔧 **Troubleshooting**

### **Common Issues**

#### **"Unsupported version" Error**
- **Cause**: Collection uses v1.0 or v3.0+ format
- **Solution**: Re-export from Postman using v2.1 format

#### **"No valid requests" Error**
- **Cause**: Malformed request structures
- **Solution**: Check request URLs and methods in Postman

#### **"Unsupported features" Error**
- **Cause**: Collection uses scripts or advanced auth
- **Solution**: Remove scripts and simplify authentication

#### **Variables Not Working**
- **Cause**: Variable format differences
- **Solution**: Check variable names and update values after import

### **Validation Process**
The import process validates collections in this order:

1. **JSON Format** - Valid JSON structure
2. **Collection Schema** - Postman collection format
3. **Version Check** - Supported version (v2.0-v2.2)
4. **Structure Validation** - Required fields present
5. **Feature Check** - No unsupported features
6. **Request Validation** - Valid HTTP requests

## 📊 **Compatibility Matrix**

| Feature Category | Support Level | Notes |
|------------------|---------------|-------|
| **Basic Collections** | 🟢 Full | Complete support |
| **Authentication** | 🟡 Partial | Common methods only |
| **Request Bodies** | 🟢 Full | All standard types |
| **Variables** | 🟡 Partial | Static variables only |
| **Scripts** | 🔴 None | Not supported |
| **Environments** | 🔴 None | Use collection variables |
| **File Uploads** | 🔴 None | Use form data instead |

**Legend:**
- 🟢 Full Support - All features work
- 🟡 Partial Support - Common features work
- 🔴 No Support - Feature not available

---

**Last Updated**: 2025-01-03  
**API Connector Version**: 1.1.0+  
**Postman Compatibility**: v2.0, v2.1, v2.2
