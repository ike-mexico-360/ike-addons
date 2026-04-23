{
    'name': 'Events API',
    'version': '18.0.1.0.0',
    'category': 'Custom',
    'summary': 'API endponit para interacción de eventos',
    'description': """
        Módulo que expone un endpoint REST API para crear eventos
    """,
    'author': 'AlsibaMX',
    'license': 'LGPL-3',
    'depends': [
        'ike_event',
        'custom_nu',
        'ike_event_membership_authorization',
    ],
    'data': [
        "security/ir.model.access.csv",
        "views/ike_event_screen_views.xml",
        "views/ike_event_views.xml",
        "views/custom_membership_plan_views.xml",
        "views/custom_membership_nus_views.xml",
        "views/ike_event_service_count_views.xml",
        "wizard/ike_event_service_assistview_views.xml",
        "report/ike_event_end_service_report.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'ike_event_api/static/src/views/*.*',
            'ike_event_api/static/src/views/assistview/*.*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
