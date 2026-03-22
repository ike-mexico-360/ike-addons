# -*- coding: utf-8 -*-
{
    'name': 'IKE Event Membership Authorization',
    'summary': '''''',
    'author': '',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.3',
    'depends': [
        'base', 'web',
        'custom_nu', 'ike_event',
    ],
    'assets': {
        'web.assets_backend': [
            'ike_event_membership_authorization/static/src/fields/image_clipboard/ike_image_clipboard_field.js',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/mail_authorization_template.xml',
        'data/mail_commercial_authorization_template.xml',
        'data/mail_authorization_rejected_template.xml',
        'wizard/ike_event_add_affiliation_user_wizard.xml',
        'wizard/ike_event_membership_authorization_wizard.xml',
        "views/ike_event_screen_views.xml",
        "views/ike_event_authorization_views.xml",
        "views/ike_event_membership_authorization_views.xml",
        'views/ike_menus.xml',
    ],
}
