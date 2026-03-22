# -*- coding: utf-8 -*-

SERVICE_MODEL = {
    'ike.service.input.vial': 'custom_master_catalog.ike_product_category_vial',
    'ike.service.input.medical': 'custom_master_catalog.ike_product_category_medical',
}
SUB_SERVICE_MODEL = {
    'ike.service.input.vial.truck': 'custom_master_catalog.ike_product_product_vial_truck',
    'ike.service.input.medical.consultation': 'custom_master_catalog.ike_product_product_medical_consultation',
}

EVENT_FLOW = {
    'draft': {
        '1': {
            'sections': ['user_data'],
            'actions': ['action_set_user_data'],
        },
    },
    'capturing': {
        '1': {
            'sections': ['service_data'],
            'actions': ['action_set_service_data'],
            'summary': {
                'bottom': ['event_summary_service_data'],
            },
        },
        '2': {
            'sections': ['user_service_data'],
            'actions': ['action_set_user_service_data'],
            'summary': {
                'top': [],
                'bottom': ['event_summary_service_data'],
            },
        },
        '3': {
            'sections': ['user_service_data', 'location_data'],
            'actions': ['action_set_location_data'],
            'summary': {
                'top': ['event_summary_service_data'],
                'bottom': ['event_summary_user_service_data'],
            },
        },
        '4': {
            'sections': ['survey_data'],
            'actions': ['action_set_survey_data'],
            'summary': {
                'top': [
                    'event_summary_service_data',
                    'event_summary_user_service_data',
                ],
                'bottom': ['event_summary_location_data'],
            },
        },
        '5': {
            'service_specific': {
                'ike.service.input.vial.truck': {
                    'sections': ['destination_data'],
                    'actions': ['action_set_destination_data'],
                    'summary': {
                        'top': [
                            'event_summary_service_data',
                            'event_summary_user_service_data',
                            'event_summary_location_data',
                        ],
                        'bottom': ['event_summary_survey_data'],
                    },
                },
            },
        },
        '6': {
            'sections': ['user_sub_service_data', 'product_data'],
            'actions': ['action_set_user_sub_service_data'],
            'summary': {
                'top': [
                    'event_summary_service_data',
                    'event_summary_user_service_data',
                    'event_summary_location_data',
                ],
                'bottom': ['event_summary_survey_data'],
            },
        },
    },
    'searching': {
        '1': {
            'sections': ['supplier_data'],
            'service_stage': 'preparing',
            'actions': ['action_set_supplier_data'],
            'summary': {
                'top': [
                    'event_summary_service_data',
                    'event_summary_user_service_data',
                    'event_summary_location_data',
                    'event_summary_survey_data',
                ],
                'bottom': [],
            },
        },
        '2': {
            'description': 'Testing Purpose',
            'sections': [''],
            'domain': [
                '|',
                ('service_ref', '=', 'test'),
                ('service_ref', '=', 'test2'),
            ],
            'service_stage': 'assigned',
            'summary': {
                'top': [
                    'event_summary_service_data',
                    'event_summary_user_service_data',
                    'event_summary_location_data',
                ],
                'bottom': ['event_summary_supplier_data'],
            },
        },
    },
    'assigned': {
        '1': {
            'sections': [''],
            'summary': {
                'top': [
                    'event_summary_service_data',
                    'event_summary_user_service_data',
                    'event_summary_location_data',
                    'event_summary_user_sub_service_data',
                    'event_summary_supplier_data',
                ],
                'bottom': [],
            },
        },
    },
    'in_progress': {
        '1': {
            'sections': [''],
            'summary': {
                'top': [
                    'event_summary_service_data',
                    'event_summary_user_service_data',
                    'event_summary_location_data',
                    'event_summary_user_sub_service_data',
                ],
                'bottom': [],
            },
        },
    },
    'completed': {
        '1': {
            'sections': [''],
            'summary': {
                'top': [
                    'event_summary_service_data',
                    'event_summary_user_service_data',
                    'event_summary_location_data',
                    'event_summary_user_sub_service_data',
                ],
                'bottom': [],
            },
        },
    },
    'cancel': {
        '1': {
            'sections': [''],
            'summary': {
                'top': [
                    'event_summary_service_data',
                    'event_summary_user_service_data',
                    'event_summary_location_data',
                    'event_summary_user_sub_service_data',
                ],
                'bottom': [],
            },
        },
    },
}
