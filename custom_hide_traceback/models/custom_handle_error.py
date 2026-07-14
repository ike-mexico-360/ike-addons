import logging
import odoo.http
from odoo.tools import exception_to_unicode

_logger = logging.getLogger(__name__)


_original_handle_error = odoo.http.JsonRPCDispatcher.handle_error
_original_serialize_exception = odoo.http.serialize_exception


def custom_handle_error(self, exc):
    """
    Global JSON-RPC Exception Handler

    Covers:
    - Odoo Web Client
    - Browser Network Responses
    - Postman JSON-RPC APIs
    - Custom Odoo APIs (type='json')

    Hides:
    - traceback
    - debug
    - file paths
    - model names
    - addon names
    """

    _logger.exception("Unhandled Exception", exc_info=exc)
    _logger.error("CUSTOM HANDLE ERROR CALLED")
    return _original_handle_error(self, exc)


def custom_serialize_exception(exception):
    name = type(exception).__name__
    module = type(exception).__module__
    return {
        'name': f'{module}.{name}' if module else name,
        # 'debug': traceback.format_exc(),
        'debug': '',
        'message': exception_to_unicode(exception),
        'arguments': exception.args,
        'context': getattr(exception, 'context', {}),
    }


odoo.http.JsonRPCDispatcher.handle_error = custom_handle_error
odoo.http.serialize_exception = custom_serialize_exception
