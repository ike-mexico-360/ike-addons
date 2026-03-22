# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
import json


@tagged('standard', 'at_install')
class TestPostmanImport(TransactionCase):
    """Test Postman collection import functionality"""

    def setUp(self):
        super().setUp()
        self.parser = self.env['postman.parser']

    def test_postman_collection_validation(self):
        """Test Postman collection validation"""

        # Valid Postman collection
        valid_collection = {
            "info": {
                "name": "Test Collection",
                "description": "Test description",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": []
        }

        is_valid, message = self.parser.validate_postman_collection(valid_collection)
        self.assertTrue(is_valid)

        # Invalid collection (missing info)
        invalid_collection = {
            "item": []
        }

        is_valid, message = self.parser.validate_postman_collection(invalid_collection)
        self.assertFalse(is_valid)
        self.assertIn("info", message)

    def test_simple_postman_parsing(self):
        """Test parsing a simple Postman collection"""

        postman_collection = {
            "info": {
                "name": "Simple API",
                "description": "Simple test API"
            },
            "item": [
                {
                    "name": "Get Users",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "https://api.example.com/users",
                            "protocol": "https",
                            "host": ["api", "example", "com"],
                            "path": ["users"]
                        }
                    }
                },
                {
                    "name": "Create User",
                    "request": {
                        "method": "POST",
                        "url": {
                            "raw": "https://api.example.com/users",
                            "protocol": "https",
                            "host": ["api", "example", "com"],
                            "path": ["users"]
                        },
                        "body": {
                            "mode": "raw",
                            "raw": "{\"name\": \"John Doe\", \"email\": \"john@example.com\"}"
                        }
                    }
                }
            ]
        }

        result = self.parser.parse_collection(postman_collection)

        # Check collection data
        self.assertEqual(result['name'], 'Simple API')
        self.assertEqual(result['description'], 'Simple test API')
        self.assertEqual(result['base_url'], 'https://api.example.com')

        # Check connectors
        connectors = result['connectors']
        self.assertEqual(len(connectors), 2)

        # Check first connector (GET)
        get_connector = connectors[0]
        self.assertEqual(get_connector['name'], 'Get Users')
        self.assertEqual(get_connector['method'], 'GET')
        self.assertEqual(get_connector['endpoint_path'], '/users')
        self.assertTrue(get_connector['use_collection_url'])

        # Check second connector (POST)
        post_connector = connectors[1]
        self.assertEqual(post_connector['name'], 'Create User')
        self.assertEqual(post_connector['method'], 'POST')
        self.assertEqual(post_connector['endpoint_path'], '/users')
        self.assertEqual(post_connector['request_body_type'], 'json')
        self.assertIn('John Doe', post_connector['request_body'])

    def test_postman_with_variables(self):
        """Test parsing Postman collection with variables"""

        postman_collection = {
            "info": {
                "name": "API with Variables"
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": "https://api.example.com"
                },
                {
                    "key": "api_version",
                    "value": "v1"
                }
            ],
            "item": [
                {
                    "name": "Get User by ID",
                    "request": {
                        "method": "GET",
                        "url": {
                            "raw": "{{base_url}}/{{api_version}}/users/{{user_id}}",
                            "path": ["{{api_version}}", "users", "{{user_id}}"]
                        }
                    }
                }
            ]
        }

        result = self.parser.parse_collection(postman_collection)

        # Check collection variables
        variables = json.loads(result['collection_variables'])
        self.assertEqual(variables['base_url'], 'https://api.example.com')
        self.assertEqual(variables['api_version'], 'v1')

        # Check connector with converted variables
        connector = result['connectors'][0]
        self.assertEqual(connector['endpoint_path'], '/{api_version}/users/{user_id}')

        # Check endpoint variables
        endpoint_vars = json.loads(connector['endpoint_variables'])
        self.assertIn('user_id', endpoint_vars)

    def test_postman_with_auth(self):
        """Test parsing Postman collection with authentication"""

        postman_collection = {
            "info": {
                "name": "API with Auth"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "test-token-123"
                    }
                ]
            },
            "item": [
                {
                    "name": "Protected Endpoint",
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/protected"
                    }
                }
            ]
        }

        result = self.parser.parse_collection(postman_collection)

        # Check auth configuration
        self.assertEqual(result['auth_type'], 'bearer')
        self.assertEqual(result['auth_token'], 'test-token-123')

    def test_postman_folders(self):
        """Test parsing Postman collection with folders"""

        postman_collection = {
            "info": {
                "name": "API with Folders"
            },
            "item": [
                {
                    "name": "Users",
                    "item": [
                        {
                            "name": "Get User",
                            "request": {
                                "method": "GET",
                                "url": "https://api.example.com/users/1"
                            }
                        },
                        {
                            "name": "Update User",
                            "request": {
                                "method": "PUT",
                                "url": "https://api.example.com/users/1"
                            }
                        }
                    ]
                },
                {
                    "name": "Orders",
                    "item": [
                        {
                            "name": "Get Orders",
                            "request": {
                                "method": "GET",
                                "url": "https://api.example.com/orders"
                            }
                        }
                    ]
                }
            ]
        }

        result = self.parser.parse_collection(postman_collection)

        # Check connectors with folder names
        connectors = result['connectors']
        self.assertEqual(len(connectors), 3)

        # Check folder prefixes in names
        self.assertEqual(connectors[0]['name'], 'Users - Get User')
        self.assertEqual(connectors[1]['name'], 'Users - Update User')
        self.assertEqual(connectors[2]['name'], 'Orders - Get Orders')

    def test_invalid_postman_data(self):
        """Test error handling for invalid Postman data"""

        # Test invalid JSON
        with self.assertRaises(UserError):
            self.parser.parse_collection("invalid json")

        # Test missing info section
        with self.assertRaises(UserError):
            self.parser.parse_collection({"item": []})

    def test_unsupported_postman_versions(self):
        """Test handling of unsupported Postman versions"""

        # Unsupported version
        unsupported_collection = {
            "info": {
                "name": "Future Collection",
                "schema": "https://schema.getpostman.com/json/collection/v3.0.0/collection.json"
            },
            "item": []
        }

        is_valid, message = self.parser.validate_postman_collection(unsupported_collection)
        self.assertFalse(is_valid)
        self.assertIn("v3.0", message)
        self.assertIn("Supported versions", message)

    def test_unsupported_postman_features(self):
        """Test detection of unsupported Postman features"""

        # Collection with unsupported auth
        collection_with_unsupported_auth = {
            "info": {
                "name": "NTLM Collection",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "ntlm",
                "ntlm": [{"key": "username", "value": "user"}]
            },
            "item": []
        }

        is_valid, message = self.parser.validate_postman_collection(collection_with_unsupported_auth)
        self.assertFalse(is_valid)
        self.assertIn("unsupported features", message)
        self.assertIn("ntlm", message)

    def test_empty_postman_collection(self):
        """Test handling of empty Postman collections"""

        empty_collection = {
            "info": {
                "name": "Empty Collection",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": []
        }

        is_valid, message = self.parser.validate_postman_collection(empty_collection)
        self.assertFalse(is_valid)
        self.assertIn("empty", message.lower())

    def test_malformed_postman_requests(self):
        """Test handling of malformed requests in Postman collection"""

        malformed_collection = {
            "info": {
                "name": "Malformed Collection",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "item": [
                {
                    "name": "Invalid Request",
                    "request": {
                        # Missing both URL and method
                    }
                }
            ]
        }

        is_valid, message = self.parser.validate_postman_collection(malformed_collection)
        self.assertFalse(is_valid)
        self.assertIn("No valid requests", message)

    def test_postman_collection_with_scripts(self):
        """Test detection of Postman collections with scripts"""

        collection_with_scripts = {
            "info": {
                "name": "Collection with Scripts",
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "event": [
                {
                    "listen": "prerequest",
                    "script": {
                        "exec": ["console.log('pre-request script');"]
                    }
                }
            ],
            "item": [
                {
                    "name": "Simple Request",
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/test"
                    }
                }
            ]
        }

        is_valid, message = self.parser.validate_postman_collection(collection_with_scripts)
        self.assertFalse(is_valid)
        self.assertIn("Pre-request scripts", message)

    def test_postman_validation_detailed_messages(self):
        """Test that validation provides detailed, helpful error messages"""

        # Test various invalid scenarios
        test_cases = [
            (
                {"not_a_collection": True},
                "Missing 'info' section"
            ),
            (
                {"info": {"no_name": True}},
                "missing collection name"
            ),
            (
                {
                    "info": {"name": "Test", "schema": "not-postman-schema"},
                    "item": []
                },
                "not a Postman collection"
            )
        ]

        for invalid_data, expected_error_part in test_cases:
            is_valid, message = self.parser.validate_postman_collection(invalid_data)
            self.assertFalse(is_valid)
            self.assertIn(expected_error_part.lower(), message.lower())

    def test_postman_graphql_request(self):
        """Test parsing Postman GraphQL request"""

        postman_collection = {
            "info": {
                "name": "GraphQL API"
            },
            "item": [
                {
                    "name": "GraphQL Query",
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/graphql",
                        "body": {
                            "mode": "graphql",
                            "graphql": {
                                "query": "query GetUsers { users { id name email } }",
                                "variables": "{\"limit\": 10}"
                            }
                        }
                    }
                }
            ]
        }

        result = self.parser.parse_collection(postman_collection)

        connector = result['connectors'][0]
        self.assertEqual(connector['request_body_type'], 'json')

        # Check GraphQL query is properly formatted
        body = json.loads(connector['request_body'])
        self.assertIn('query', body)
        self.assertIn('variables', body)
        self.assertEqual(body['variables']['limit'], 10)
