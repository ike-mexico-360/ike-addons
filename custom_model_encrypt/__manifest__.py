# -*- coding: utf-8 -*-

{
    'name': "Custom Model Encryption",
    'summary': """Custom Model Encryption""",
    'author': "AlsibaMx",
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.0',
    'depends': [
        'base',
        'mail',
    ],
    'post_init_hook': '_custom_encrypt_post_init',
    "data": [],
    'external_dependencies': {'python': ['pycryptodome']},
}
