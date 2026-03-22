from odoo import models  # , fields
# from odoo.tools import float_round
import logging
_logger = logging.getLogger(__name__)


class EmpPerf360Report(models.AbstractModel):
    _name = 'report.ike_event_api.report_ike_event_end_service_document'
    _description = 'End Service Report'

    def _get_report_values(self, docids, data=None):
        docs = self.env['ike.event'].browse(docids)
        # Lógica avanzada
        return {'docs': docs}
