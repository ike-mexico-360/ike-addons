# -*- coding: utf-8 -*-
{
    'name': "IKE Events Binnacle",
    'summary': """""",
    'author': "AlsibaMx",
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.1',
    'depends': [
        'base',
        'web',
        'mail',
        'custom_master_catalog',
        'ike_event',
        'ike_event_membership_authorization',
    ],
    "data": [
        "data/ike_event_binnacle_data.xml",
        "security/ir.model.access.csv",
        "views/ike_event_binnacle_category_views.xml",
        "views/ike_event_binnacle_views.xml",
        "views/ike_event_screen_views.xml",
        "views/mail_message_views.xml",
        "wizard/ike_event_comment_wizard_views.xml",
        "views/ike_menus.xml",
        'security/cleanup_menus.xml',  # TODO Delete in sprint18 or after the client has updated their database with this code
    ],
    'assets': {
        'web.assets_backend': [
            'ike_event_binnacle/static/src/css/styles.css',
            'ike_event_binnacle/static/src/widgets/binnacle_widget/binnacle_widget.js',
            'ike_event_binnacle/static/src/widgets/binnacle_widget/binnacle_widget.xml',
        ],
    },
}
