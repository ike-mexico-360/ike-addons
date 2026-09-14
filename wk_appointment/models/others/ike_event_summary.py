from odoo import models, _


class IkeEventSummary(models.Model):
    _inherit = 'ike.event.summary'

    def set_service_data(self):
        result = super().set_service_data()

        for rec in self:
            event = rec.event_id
            service_data = dict(rec.service_data or {})
            fields_data = list(service_data.get('fields', []))

            appointment_fields = [{
                'name': 'scheduled',
                'string': event.fields_get(['scheduled'])['scheduled']['string'],
                'type': 'char',
                'value': (_('Yes') if event.scheduled else _('No')),  # type: ignore
            }]

            if event.scheduled and event.event_date:  # type: ignore
                appointment_fields.append({
                    'name': 'event_date',
                    'string': _('Event date'),
                    'type': event.fields_get(['event_date'])['event_date']['type'],
                    'value': event.event_date.strftime('%Y-%m-%d %H:%M:%S'),
                })

            # Insertar después de Open date.
            position = next(
                (
                    index + 1
                    for index, field_data in enumerate(fields_data)
                    if field_data.get('name') == 'create_date'
                ),
                len(fields_data),
            )

            fields_data[position:position] = appointment_fields
            service_data['fields'] = fields_data
            rec.service_data = service_data

        return result
