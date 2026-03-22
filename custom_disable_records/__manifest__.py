# -*- coding: utf-8 -*-
{
    'name': "Custom Disable Records",
    'summary': """""",
    'author': "Neftalí Michelet",
    'website': "https://www.linkedin.com/in/neftalimich",
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.0',
    'depends': ['base', 'web', 'mail'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            'custom_disable_records/static/src/relational_model/*.*',
            'custom_disable_records/static/src/confirmation_dialog/*.*',
            'custom_disable_records/static/src/form/*.*',
            'custom_disable_records/static/src/list/*.*',
            'custom_disable_records/static/src/fields/*.*',
        ],
    },
}
