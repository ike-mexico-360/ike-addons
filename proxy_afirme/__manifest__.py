# -*- coding: utf-8 -*-
{
    'name': "Proxy AFIRME",

    'summary': "Modulo que sirve como Proxy para consumo del Graphql de SISE MX",

    'description': """
        Modulo que sirve como Proxy para consumo del Graphql de SISE que expone los expedientes viales de las cuentas del proveedor AFIRME
    """,

    'author': "Lenin Franco",
    'website': "https://www.lefranco.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Tools',
    'version': '0.1',
    'installable': True,
    'auto_install': False,

    # any module necessary for this one to work correctly
    'depends': ['base', 'portal'],

    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
        'views/tablero_afirme_template.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'proxy_afirme/static/src/scss/afirme_dashboard.scss',
            'proxy_afirme/static/src/js/afirme_dashboard.js',
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}

