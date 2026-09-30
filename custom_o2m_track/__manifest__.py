# -*- coding: utf-8 -*-
{
    'name': "One2many Field Detailed Tracking",
    'summary': """Track One2many fields detailed""",
    'author': "Neftalí Michelet",
    'website': "https://www.linkedin.com/in/neftalimich",
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.1',
    'depends': ['base', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/mail_message_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_o2m_track/static/src/core/web/message_patch.xml',
            'custom_o2m_track/static/src/core/web/message_patch.js',
        ],
    },
}
