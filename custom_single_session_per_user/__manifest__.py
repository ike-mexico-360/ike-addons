# -*- coding: utf-8 -*-
{
    'name': 'Custom Single Session Per User',
    'version': '18.0.1.0.0',
    'category': 'Authentication',
    'summary': 'Close all previous sessions when user logs in from new device',
    'description': """
        This module automatically closes all previous sessions when a user
        logs in from a new device or browser using Odoo's native session management.
    """,
    'author': 'lumpuy@hotmail.com',
    'depends': ['base', 'web', 'custom_master_catalog',],
    'data': [
        'security/ir_module_security.xml',
        'security/ir.model.access.csv',
        'views/res_groups_views.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
