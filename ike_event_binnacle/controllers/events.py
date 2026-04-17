from markupsafe import Markup
from odoo import http, _
from odoo.http import request
from werkzeug.exceptions import (Forbidden, BadRequest, InternalServerError, Unauthorized)  # noqa: F401  # type: ignore

import logging
_logger = logging.getLogger(__name__)


class EventAPIController(http.Controller):

    # =================== #
    #    SUPPLIER LOG     #
    # =================== #
    @http.route('/ike/catalog/supplier_log', type='json', auth='user', methods=['GET'])
    def ike_catalog_supplier_log(self, **kw):
        if not request.env.uid:
            request.env.cr.rollback()
            raise Unauthorized('Usuario no autenticado')
        comments = request.env['ike.event.default.supplier_comment'].search_read([('disabled', '=', False)], ['id', 'name'])
        return comments

    @http.route('/ike/event/supplier_log/set', type='json', auth='user', methods=['POST'])
    def ike_event_vehicle_send_collection(self, **kw):
        event_id = kw.get('event_id', False)
        supplier_data = kw.get('supplier', {})
        comments = kw.get('comments', False)

        if not event_id or not comments:
            raise BadRequest(_('Missing parameters'))

        try:
            html_comments = Markup(comments)

            ctx = {
                'body_html_content': html_comments,
            }

            supplier_name = supplier_data.get('name', False)
            if supplier_name:
                ctx.update({
                    'supplier': supplier_name
                })

            event = request.env['ike.event'].sudo().browse(event_id)
            event.with_context(
                dict(ctx)
            )._create_message_binnacle(binnacle_xmlids=['ike_event_binnacle.ike_binnacle_api_msg'])
            return {'status': 'success', 'message': _('Comment sent successfully')}
        except Exception as e:
            _logger.error(f"Error on action_save_external_message: {str(e)}")
            raise InternalServerError(str(e))
