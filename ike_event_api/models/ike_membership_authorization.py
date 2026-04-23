from odoo import models
import logging
import requests

_logger = logging.getLogger(__name__)


class IkeMembershipAuthorization(models.Model):
    _inherit = 'ike.event.membership.authorization'

    def action_authorized(self):
        res = super().action_authorized()
        for rec in self:
            # nus_membership_id
            plan_id = rec.nus_membership_id.membership_plan_id
            affiliation_id = rec.nus_membership_id
            affiliation_detail_ids = affiliation_id.event_count_detail_ids
            to_process_details = affiliation_detail_ids.filtered(lambda x: not x.x_saved_external_totals)
            url = plan_id.x_event_totalizer_endpoint_url
            connect_to_external = affiliation_id.x_service_counter_validation
            decrypt_encrypt_utility_sudo = self.env['custom.encryption.utility'].sudo()
            _logger.warning(f"{rec.key_identification} {rec.account_id.name} {rec.affiliation_date_start.isoformat()} {rec.affiliation_date_end.isoformat()} {url} {connect_to_external} {decrypt_encrypt_utility_sudo.decrypt_aes256(affiliation_id.name)}")
            if (rec.key_identification and rec.account_id and rec.affiliation_date_start and rec.affiliation_date_end
                    and url and connect_to_external and len(affiliation_detail_ids) > 0):
                policy = f"{rec.key_identification.strip()}-{rec.clause_primary.strip() if rec.clause_primary else '0'}"
                payload = {
                    "poliza": policy,
                    "fecha_inicial": rec.affiliation_date_start.isoformat(),
                    "fecha_final": rec.affiliation_date_end.isoformat(),
                }
                _logger.warning(f"{payload}")
                try:
                    response = requests.post(
                        url,
                        headers={
                            "Content-Type": "application/json",
                            "User-Agent": "Python-IoT-Test/1.0",
                        },
                        json=payload,
                    )
                    data = response.json()
                    details = data.get('detalle', [])
                    matching_details = [r for r in details if r['poliza'].strip() == policy]
                    _logger.warning(f"{matching_details}")

                    for detail in matching_details:
                        # Normalizar "sub_servicio", minúsculas
                        incoming_sub_sevice = detail['sub_servicio'].strip().lower()
                        # filtrar lineas normalizando nombres de subservicios, minúsculas
                        internal_sub_sevices = to_process_details.filtered(
                            lambda x: incoming_sub_sevice.lower() in [s.lower() for s in x.sub_service_ids.mapped('name')]
                        )
                        # Si hay match:
                        for internal_sub_sevice in internal_sub_sevices:
                            internal_sub_sevice.write({
                                'total_events': detail['total'],  # actualizar total_events-> total
                                'events_of_period': detail['tt'],  # actualizar events_of_period -> tt
                                'x_saved_external_totals': True,  # marcar x_saved_external_totals -> True
                            })
                    # _logger.warning(f"{data}")
                except Exception as e:
                    _logger.error(f"Error sending service counter validation: {str(e)}")
        return res
