# -*- coding: utf-8 -*-
{
    'name': 'Custom SAT CFDI Validator Service',
    'version': '18.0.1.0.0',
    'summary': 'Technical testing of the SAT Mexico SOAP Web Service connection',
    'category': 'Technical',
    'author': 'Odoo Developer',
    'depends': [
        'base',
        'mail',
        'purchase',
        'custom_master_catalog',
        'ike_event_portal',
        'ike_event_purchase'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        # 'views/custom_sat_validator_views.xml',
        # 'views/portal_purchase_template.xml',
    ],
    # "assets": {
    #     'web.assets_frontend': [
    #         'custom_sat_validator/static/src/js/components/purchase_order_details/*.*',
    #     ],
    # },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}