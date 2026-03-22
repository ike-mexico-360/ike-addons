import logging
_logger = logging.getLogger(__name__)

def migrate(cr, version):
    # from odoo import api, SUPERUSER_ID

    # env = api.Environment(cr, SUPERUSER_ID, {})

    _logger.info("----- Cleaning summary data -----")
    cr.execute("""
        UPDATE ike_event_summary
        SET user_data = NULL,
            service_data = NULL,
            user_service_data = NULL,
            location_data = NULL,
            survey_data = NULL,
            supplier_data = NULL,
            user_sub_service_data = NULL,
            event_data = NULL
    """)
    cr.commit()
    _logger.info("----- Cleaning sections data -----")
    cr.execute("""
        UPDATE ike_event
        SET sections = NULL
    """)
    cr.commit()
