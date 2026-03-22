# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import models, fields, api, Command, _
from odoo.exceptions import UserError


class IkeEventSummary(models.Model):
    _name = 'ike.event.summary'
    _description = 'Event Summary'
    _rec_name = 'event_id'

    event_id = fields.Many2one('ike.event', ondelete='cascade', required=True)

    user_data = fields.Json()
    service_data = fields.Json()
    user_service_data = fields.Json()
    location_data = fields.Json()
    survey_data = fields.Json()
    supplier_data = fields.Json()
    user_sub_service_data = fields.Json()
    event_data = fields.Json()

    def set_user_data(self):
        for rec in self:
            rec.service_data = {
                'title': f"<h4 class='text-ike-primary'>{_('Expedient')}</span></h4>",
                'fields': [
                    {
                        'name': 'folio_name',
                        'string': _('Folio'),
                        'type': 'char',
                        'value': rec.event_id.name,
                    },
                    {
                        'name': 'event_date',
                        'string': rec.event_id.fields_get(['event_date'])['event_date']['string'],
                        'type': rec.event_id.fields_get(['event_date'])['event_date']['type'],
                        'value': rec.event_id.event_date.strftime('%Y-%m-%d %H:%M:%S') if rec.event_id.event_date else False,
                    },
                ]
            }

    def set_service_data(self):
        for rec in self:
            rec.service_data = {
                'title': f"<h4 class='text-ike-primary'>{_('Expedient')}:</span></h4>",
                'fields': [
                    {
                        'name': 'folio_name',
                        'string': _('Folio'),
                        'type': 'char',
                        'value': rec.event_id.name,
                    },
                    {
                        'name': 'event_date',
                        'string': rec.event_id.fields_get(['event_date'])['event_date']['string'],
                        'type': rec.event_id.fields_get(['event_date'])['event_date']['type'],
                        'value': rec.event_id.event_date.strftime('%Y-%m-%d %H:%M:%S') if rec.event_id.event_date else False,
                    },
                    {
                        'name': 'service_id',
                        'string': rec.event_id.fields_get(['service_id'])['service_id']['string'],
                        'type': 'char',
                        'value': rec.event_id.service_id.name,
                    },
                    {
                        'name': 'sub_service_id',
                        'string': rec.event_id.fields_get(['sub_service_id'])['sub_service_id']['string'],
                        'type': 'char',
                        'value': rec.event_id.sub_service_id.name,
                    },
                    {
                        'name': 'event_cost',
                        'string': rec.event_id.fields_get(['event_cost'])['event_cost']['string'],
                        'type': rec.event_id.fields_get(['event_cost'])['event_cost']['type'],
                        'value': rec.event_id.event_cost,
                    },
                ]
            }

    def set_user_service_data(self):
        pass

    def set_location_data(self):
        for rec in self:
            rec.location_data = {
                'title': f"<h4 class='text-ike-primary'>{_('Location')}:</h4>",
                'fields': [
                    {
                        'name': 'location_label',
                        'string': rec.event_id.fields_get(['location_label'])['location_label']['string'],
                        'type': 'html',
                        'value': rec.event_id.location_label,
                    },
                ]
            }

    def set_survey_data(self):
        pass

    def set_destination_data(self):
        for rec in self:
            rec.set_location_data()
            location_data = rec.location_data
            fields = location_data.get('fields', [])
            fields.extend([
                {
                    'name': 'destination_label',
                    'string': rec.event_id.fields_get(['destination_label'])['destination_label']['string'],
                    'type': 'html',
                    'value': rec.event_id.destination_label,
                },
                {
                    'name': 'destination_distance',
                    'string': _('Distance'),
                    'type': 'char',  # This is a hack to avoid the float to be rendered as a string
                    'value': f"{round(rec.event_id.destination_distance, 3)} km",
                },
                {
                    'name': 'destination_duration',
                    'string': _('Duration'),
                    'type': 'char',  # This is a hack to avoid the float to be rendered as a string
                    'value': f"{int(rec.event_id.destination_duration)} min",
                },
            ])
            location_data['fields'] = fields
            rec.location_data = location_data

    def set_user_sub_service_data(self):
        for rec in self:
            rec.user_sub_service_data = False

    def set_supplier_data(self):
        assignation_types = dict(self.env['ike.event.supplier']._fields['assignation_type'].get_description(self.env)['selection'])
        for rec in self:

            supplier_data = {
                'title': f"<h4 class='text-ike-primary'>{_('Supplier assignment')}</h4>",
                'fields': [],
            }
            if rec.event_id.selected_supplier_ids:
                index = 0
                for service_supplier_id in rec.event_id.selected_supplier_ids:
                    # Duration
                    assignation_minutes = (service_supplier_id.acceptance_duration or 0) // 60
                    assignation_seconds = (service_supplier_id.acceptance_duration or 0) % 60

                    global_fields = [
                        {
                            'name': 'supplier_id_' + str(index),
                            'string': _('Supplier'),
                            'type': 'char',
                            'value': service_supplier_id.supplier_id.display_name,
                        },
                        {
                            'name': 'assigned_' + str(index),
                            'string': _('Assigned'),
                            'type': 'char',
                            'value': service_supplier_id.assigned,
                        },
                        {
                            'name': 'estimated_duration_' + str(index),
                            'string': _('Estimated Duration'),
                            'type': 'char',
                            'value': str(int(service_supplier_id.estimated_duration)) + " min",
                        },
                        {
                            'name': 'assignation_type_' + str(index),
                            'string': _('Assignation Type'),
                            'type': 'char',
                            'value': assignation_types.get(service_supplier_id.assignation_type),
                        },
                        {
                            'name': 'assignation_duration_' + str(index),
                            'string': _('Assignation Duration'),
                            'type': 'char',
                            'value': _("%s minutes %s seconds") % (assignation_minutes, assignation_seconds),
                        },
                    ]

                    supplier_data['fields'] += global_fields

                    # By Service
                    service_fields = []
                    if rec.event_id.service_ref == 'vial':
                        # Assigned string
                        supplier_data['fields'][1]['string'] = _('Operator')

                        service_fields = [
                            {
                                'name': 'service_truck_id_' + str(index),
                                'string': _('Service Vehicle'),
                                'type': 'char',
                                'value': service_supplier_id.truck_id.name,
                            },
                            {
                                'name': 'x_vehicle_type_' + str(index),
                                'string': _('Service Vehicle Type'),
                                'type': 'char',
                                'value': service_supplier_id.truck_id.x_vehicle_type.name,
                            },
                            {
                                'name': 'plate_' + str(index),
                                'string': _('Plate'),
                                'type': 'char',
                                'value': service_supplier_id.truck_id.license_plate,
                            },
                        ]
                    elif rec.event_id.service_ref == 'medical':
                        # Assigned string
                        supplier_data['fields'][1]['string'] = _('Doctor')

                    supplier_data['fields'] += service_fields

                    if supplier_data['fields']:
                        supplier_data['fields'][-1]['value'] += '<br/><br/>'
                        supplier_data['fields'][-1]['type'] = 'html'
                    index += 1

                # Save field
                rec.supplier_data = supplier_data

    def set_event_data(self):
        for rec in self:
            event_data = {
                'title': f"<h4><span class='text-ike-primary'>{_('Summary')}</span></h4>",
                'fields': []
            }
            distance = 0.0
            duration = 0.0
            if rec.event_id.location_label:
                event_data['fields'].append({
                    'name': 'location_label',
                    'string': rec.event_id.fields_get(['location_label'])['location_label']['string'],
                    'type': 'html',
                    'value': rec.event_id.location_label,
                })
            if rec.event_id.destination_label:
                event_data['fields'].append({
                    'name': 'destination_label',
                    'string': rec.event_id.fields_get(['destination_label'])['destination_label']['string'],
                    'type': 'html',
                    'value': rec.event_id.destination_label,
                })
                distance += rec.event_id.destination_distance
                duration += rec.event_id.destination_duration
            if distance:
                event_data['fields'].append({
                    'name': 'distance',
                    'string': _('Distance'),  # Field not exist in db
                    'type': 'char',  # This is a hack to avoid the float to be rendered as a string
                    'value': f"{round(distance / 1000, 3)} km",
                })
            if duration:
                event_data['fields'].append({
                    'name': 'duration',
                    'string': _('Duration'),  # Field not exist in db
                    'type': 'char',  # This is a hack to avoid the float to be rendered as a string
                    'value': f"{int(duration // 60)} min",
                })

            rec.event_data = event_data
