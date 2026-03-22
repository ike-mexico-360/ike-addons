{
    'name': 'Ike Events (Portal)',
    'version': '1.0',
    'description': '',
    'summary': '',
    'author': '',
    'website': '',
    'license': 'LGPL-3',
    'category': '',
    'depends': [
        'ike_event', 'ike_event_api', 'custom_master_catalog', 'portal', 'web'
    ],
    'data': [
        'security/ir_module_security.xml',
        'security/ir.model.access.csv',
        'views/ike_event_portal_menuitems.xml',
        'views/ike_event_portal_suppliers_views.xml',
        'views/ike_event_portal_truck_views.xml',
        'views/ike_event_portal_user_views.xml',
        'views/ike_event_portal_services.xml',
        'views/ike_event_public_views.xml',
        'views/ike_event_views.xml'
    ],
    'assets': {
        'web.assets_frontend': [
            'ike_event_portal/static/src/css/ike_event_portal_truck_views.css',
            'ike_event_portal/static/src/css/ike_event_portal_truck_new.css',
            'ike_event_portal/static/src/scss/ike_portal.scss',
            'ike_event_portal/static/src/portal/trucks_widget_portal.js',
            'ike_event_portal/static/src/assets/GruaAzul.png',
            'ike_event_portal/static/src/react_app/dist/assets/*.js',
            'ike_event_portal/static/src/components/**/*.*',
        ]
    },
    'auto_install': False,
    'application': True,
}
