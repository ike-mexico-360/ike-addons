# -*- coding: utf-8 -*-

{
    'name': "Ike Event (Purchase)",
    'summary': """Custom NU""",
    'author': "AlsibaMx",
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.0',
    'depends': [
        'purchase',
        'custom_master_catalog',
        'ike_event',
        'sh_all_in_one_helpdesk',
        'ike_event_portal',
        'custom_o2m_track',
    ],
    "data": [
        'security/ir.model.access.csv',
        "data/purchase_email_data.xml",
        "data/ike_event_purchase_data.xml",
        "views/ike_event_screen_views.xml",
        "views/purchase_order_views.xml",
        "views/res_partner_supplier_views.xml",
        "views/res_config_settings_views.xml",
        "views/portal_purchase_templates.xml",
        "views/sh_helpdesk_ticket_views.xml",
        "views/ike_menus.xml",
    ],
    "assets": {
        'web.assets_frontend': [
            'ike_event_purchase/static/src/js/purchase_portal_sidebar.js',
            'ike_event_purchase/static/src/js/components/purchase_order_details/*.*',
            'ike_event_purchase/static/src/js/components/purchase_order_dispute/*.*',
        ],
        'web.assets_backend': [
            'ike_event_purchase/static/src/xml/systray_notification_view.xml'
        ]
    }
}
