from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError, UserError
from unittest.mock import patch, Mock


@tagged('standard', 'at_install')
class TestApiConnector(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ApiConnector = self.env['api.connector']
        self.test_connector = self.ApiConnector.create({
            'name': 'Test API',
            'base_url': 'https://api.test.com',
            'endpoint_path': '/test',
            'api_type': 'rest',
            'method': 'GET',
            'auth_type': 'none',
            'expected_response_type': 'json',
            'timeout': 30,
        })

    def test_full_url_computation(self):
        """Test full URL computation"""
        self.assertEqual(self.test_connector.full_url, 'https://api.test.com/test')

        # Test with trailing/leading slashes
        connector = self.ApiConnector.create({
            'name': 'Test API 2',
            'base_url': 'https://api.test.com/',
            'endpoint_path': '/test/',
            'api_type': 'rest',
        })
        self.assertEqual(connector.full_url, 'https://api.test.com/test/')

    def test_success_rate_computation(self):
        """Test success rate computation"""
        self.assertEqual(self.test_connector.success_rate, 0.0)

        # Simulate some calls
        self.test_connector.write({
            'total_calls': 10,
            'success_calls': 8
        })
        self.assertEqual(self.test_connector.success_rate, 0.8)

    def test_base_url_validation(self):
        """Test base URL validation"""
        with self.assertRaises(ValidationError):
            self.ApiConnector.create({
                'name': 'Invalid URL',
                'base_url': 'invalid-url',
                'api_type': 'rest',
            })

    def test_custom_headers_validation(self):
        """Test custom headers JSON validation"""
        with self.assertRaises(ValidationError):
            self.ApiConnector.create({
                'name': 'Invalid Headers',
                'base_url': 'https://api.test.com',
                'custom_headers': 'invalid json',
                'api_type': 'rest',
            })

    def test_timeout_validation(self):
        """Test timeout validation"""
        with self.assertRaises(ValidationError):
            self.ApiConnector.create({
                'name': 'Invalid Timeout',
                'base_url': 'https://api.test.com',
                'timeout': 0,
                'api_type': 'rest',
            })

    def test_prepare_headers_no_auth(self):
        """Test header preparation without authentication"""
        headers = self.test_connector._prepare_headers()
        self.assertIsInstance(headers, dict)

    def test_prepare_headers_bearer_auth(self):
        """Test header preparation with Bearer authentication"""
        self.test_connector.write({
            'auth_type': 'bearer',
            'auth_token': 'test_token'
        })
        headers = self.test_connector._prepare_headers()
        self.assertEqual(headers['Authorization'], 'Bearer test_token')

    def test_prepare_headers_api_key(self):
        """Test header preparation with API Key authentication"""
        self.test_connector.write({
            'auth_type': 'api_key',
            'auth_token': 'test_key',
            'auth_header_name': 'X-API-Key'
        })
        headers = self.test_connector._prepare_headers()
        self.assertEqual(headers['X-API-Key'], 'test_key')

    def test_prepare_headers_custom(self):
        """Test header preparation with custom headers"""
        self.test_connector.write({
            'custom_headers': '{"Custom-Header": "custom_value", "Content-Type": "application/json"}'
        })
        headers = self.test_connector._prepare_headers()
        self.assertEqual(headers['Custom-Header'], 'custom_value')
        self.assertEqual(headers['Content-Type'], 'application/json')

    def test_prepare_auth_basic(self):
        """Test basic authentication preparation"""
        self.test_connector.write({
            'auth_type': 'basic',
            'auth_username': 'user',
            'auth_password': 'pass'
        })
        auth = self.test_connector._prepare_auth()
        self.assertEqual(auth, ('user', 'pass'))

    def test_prepare_auth_none(self):
        """Test no authentication"""
        auth = self.test_connector._prepare_auth()
        self.assertIsNone(auth)

    def test_prepare_body_json(self):
        """Test JSON body preparation"""
        self.test_connector.write({
            'request_body_type': 'json',
            'request_body': '{"key": "value", "dynamic": "{test_var}"}'
        })

        # Test without dynamic data
        body = self.test_connector._prepare_body()
        expected = {"key": "value", "dynamic": "{test_var}"}
        self.assertEqual(body, expected)

        # Test with dynamic data
        body = self.test_connector._prepare_body({'test_var': 'replaced'})
        expected = {"key": "value", "dynamic": "replaced"}
        self.assertEqual(body, expected)

    def test_prepare_body_invalid_json(self):
        """Test invalid JSON body handling"""
        self.test_connector.write({
            'request_body_type': 'json',
            'request_body': 'invalid json'
        })

        with self.assertRaises(UserError):
            self.test_connector._prepare_body()

    def test_prepare_body_raw(self):
        """Test raw body preparation"""
        self.test_connector.write({
            'request_body_type': 'raw',
            'request_body': 'raw text data'
        })

        body = self.test_connector._prepare_body()
        self.assertEqual(body, 'raw text data')

    def test_prepare_body_none(self):
        """Test no body preparation"""
        body = self.test_connector._prepare_body()
        self.assertIsNone(body)

    @patch('requests.request')
    def test_execute_call_success(self, mock_request):
        """Test successful API call execution"""
        # Mock successful response
        mock_response = Mock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True, 'data': 'test'}
        mock_request.return_value = mock_response

        result = self.test_connector.execute_call()

        # execute_call now returns True for UI refresh
        self.assertTrue(result)

        # Check that response data was stored in the connector
        self.assertTrue(self.test_connector.last_response_success)
        self.assertEqual(self.test_connector.last_response_status, 200)

    @patch('requests.request')
    def test_execute_call_failure(self, mock_request):
        """Test failed API call execution"""
        # Mock failed response
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 404
        mock_response.reason = 'Not Found'
        mock_response.json.return_value = {'error': 'Not found'}
        mock_request.return_value = mock_response

        result = self.test_connector.execute_call()

        # execute_call now returns True for UI refresh even on failure
        self.assertTrue(result)

        # Check that failure was stored in the connector
        self.assertFalse(self.test_connector.last_response_success)
        self.assertEqual(self.test_connector.last_response_status, 404)

    @patch('requests.request')
    def test_execute_call_inactive_connector(self, mock_request):
        """Test API call with inactive connector"""
        self.test_connector.active = False

        with self.assertRaises(UserError):
            self.test_connector.execute_call()

        # Ensure no request was made
        mock_request.assert_not_called()

    def test_create_rest_template(self):
        """Test REST template creation helper"""
        template = self.ApiConnector.create_rest_template(
            'Test Template',
            'https://api.example.com',
            '/v1/endpoint'
        )

        self.assertEqual(template.name, 'Test Template')
        self.assertEqual(template.base_url, 'https://api.example.com')
        self.assertEqual(template.endpoint_path, '/v1/endpoint')
        self.assertEqual(template.api_type, 'rest')
        self.assertEqual(template.method, 'GET')


@tagged('standard', 'at_install')
class TestApiCallLog(TransactionCase):

    def setUp(self):
        super().setUp()
        self.ApiConnector = self.env['api.connector']
        self.ApiCallLog = self.env['api.call.log']

        self.test_connector = self.ApiConnector.create({
            'name': 'Test API',
            'base_url': 'https://api.test.com',
            'api_type': 'rest',
        })

    def test_log_creation(self):
        """Test API call log creation"""
        log = self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'success': True,
            'status_code': 200,
            'execution_time': 1.5,
            'response_data': '{"result": "success"}'
        })

        self.assertTrue(log.success)
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.execution_time, 1.5)

    def test_display_name_computation(self):
        """Test display name computation"""
        log = self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'success': True,
            'status_code': 200,
        })

        self.assertIn('Test API', log.display_name)
        self.assertIn('SUCCESS', log.display_name)

    def test_status_icon_computation(self):
        """Test status icon computation"""
        # Success case
        log_success = self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'success': True,
            'status_code': 200,
        })
        self.assertEqual(log_success.status_icon, '✅')

        # Client error case
        log_client_error = self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'success': False,
            'status_code': 404,
        })
        self.assertEqual(log_client_error.status_icon, '❌')

        # Server error case
        log_server_error = self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'success': False,
            'status_code': 500,
        })
        self.assertEqual(log_server_error.status_icon, '💥')

    def test_response_size_computation(self):
        """Test response size computation"""
        log = self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'response_data': '{"test": "data"}'
        })

        self.assertGreater(log.response_size, 0)

    def test_formatted_data_methods(self):
        """Test formatted data display methods"""
        log = self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'request_data': '{"request": "data"}',
            'response_data': '{"response": "data"}'
        })

        formatted_request = log.get_formatted_request_data()
        formatted_response = log.get_formatted_response_data()

        self.assertIn('request', formatted_request)
        self.assertIn('response', formatted_response)

    def test_cleanup_old_logs(self):
        """Test old logs cleanup"""
        # Create some old logs (mock old dates)
        from datetime import datetime, timedelta
        old_date = datetime.now() - timedelta(days=35)

        old_log = self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'call_date': old_date,
        })

        # Run cleanup
        result = self.ApiCallLog.cleanup_old_logs(days=30)
        self.assertTrue(result)

        # Check if old log still exists (it should be deleted)
        self.assertFalse(old_log.exists())

    def test_get_statistics(self):
        """Test statistics generation"""
        # Create some test logs
        self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'success': True,
            'execution_time': 1.0,
        })
        self.ApiCallLog.create({
            'connector_id': self.test_connector.id,
            'success': False,
            'execution_time': 2.0,
        })

        stats = self.ApiCallLog.get_statistics(
            connector_id=self.test_connector.id,
            days=7
        )

        self.assertEqual(stats['total_calls'], 2)
        self.assertEqual(stats['success_calls'], 1)
        self.assertEqual(stats['failed_calls'], 1)
        self.assertEqual(stats['success_rate'], 0.5)
        self.assertEqual(stats['avg_execution_time'], 1.5)
