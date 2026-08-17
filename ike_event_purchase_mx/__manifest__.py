# -*- coding: utf-8 -*-

{
    'name': "Ike Event (Purchase México)",
    'summary': """Ike Event (Purchase México)""",
    'author': "AlsibaMx",
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.0',
    'depends': [
        'account',
        'purchase',
        'ike_event_purchase',
        'custom_sat_validator',
    ],
    "data": [
        "data/ike_event_purchase_mx_data.xml",
        "views/purchase_order_views.xml",
    ],
}
