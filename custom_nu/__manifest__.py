# -*- coding: utf-8 -*-

{
    'name': "Custom NU",
    'summary': """Custom NU""",
    'author': "AlsibaMx",
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.0',
    'depends': [
        'base',
        'custom_master_catalog',
        'custom_model_encrypt',
    ],
    "data": [
        'security/ir_module_security.xml',
        'security/ir.model.access.csv',
        'views/custom_nus_views.xml',
        'views/custom_address_type_views.xml',
        'views/custom_membership_plan_views.xml',
        'views/custom_membership_nus_views.xml',
        'views/custom_nus_vehicle_views.xml',
        'views/custom_nus_address_views.xml',
        'views/custom_nus_pet_views.xml',
        'views/custom_nus_pet_type_views.xml',
        'views/custom_nus_pet_breed_views.xml',
        'views/custom_nus_menus.xml',
        'views/custom_membership_plan_product_views.xml',
    ],
    'external_dependencies': {
        'python': ['pycryptodome']
    },
    'assets': {
        'web.assets_backend': [
            'custom_nu/static/src/fields/*.*',
            'custom_nu/static/src/widgets/**/*.*',
        ],
    },
}
