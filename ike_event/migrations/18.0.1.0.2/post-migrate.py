import sys
import os


import logging
_logger = logging.getLogger(__name__)

module_path = os.path.join(os.path.dirname(__file__), '..', '..')
sys.path.insert(0, os.path.abspath(module_path))
from constants import EVENT_FLOW


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    _logger.info("Updating sections data")
    event_ids = env['ike.event'].search([])
    event_flow_order = ['draft', 'capturing', 'searching', 'assigned', 'in_progress', 'completed', 'cancel']

    for event in event_ids:
        event._compute_sections()
        _logger.info("Computed sections for event %s", event.name)

        event_stage = event.stage_ref
        event_step = event.step_number

        for stage in event_flow_order:
            current_stage = EVENT_FLOW.get(stage, {})

            if not current_stage:
                continue

            steps = sorted(current_stage.keys())

            for step in steps:
                current_step = current_stage.get(step, None)

                actions = current_step.get('actions', [])

                service_specific = current_step.get('service_specific', {})
                service_model = 'dummy'
                if service_specific:
                    if event.service_res_model in service_specific:
                        service_model = event.service_res_model
                    elif event.sub_service_res_model in service_specific:
                        service_model = event.sub_service_res_model
                    actions = service_specific.get(service_model, {}).get('actions', [])

                for action in actions:
                    try:
                        getattr(event, action)()
                        _logger.info('Executed action %s for event %s', action, event.name)
                    except Exception as e:
                        _logger.warning('Error executing action %s for event %s: %s', action, event.name, str(e))

                if event_step == step:
                    break

            if event_stage == stage:
                break
