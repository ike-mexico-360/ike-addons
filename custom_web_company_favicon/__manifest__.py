# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Customize Company Backend web icon',
    'version': '18.0.1.0.0',
    'category': 'Extra Tools',
    'icon': '/custom_web_company_favicon/static/description/icon.png',
    'sequence': 20,
    'author': 'BB Logic',
    'summary': 'The custom web window Favicon',
    'description': """
Customize Favicon
==============================================
    """,
    'depends': ['web'],
    'data': [
        'views/res_company.xml',
    ],
    'website': 'https://bb.logic/',
    'installable': True,
    'auto_install': False,
    "application": True,
    'license': 'LGPL-3',
    'images': ["static/description/images/ss1.png", "static/description/images/ss2.png"],
    'assets': {
        'web.assets_backend': [
            'custom_web_company_favicon/static/src/js/favicon.js',
        ],
    }
}
