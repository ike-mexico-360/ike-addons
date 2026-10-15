{
    'name': 'Custom Master Catalog (Mexico)',
    'version': '1.0',
    'description': 'Complemento de custom_master_catalog para localización México',
    'summary': '',
    'author': 'AlsibaMX',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Tools',
    'depends': [
        'l10n_mx',
        'custom_master_catalog',
    ],
    'data': [
        # 'data/sub_service_data.xml',
        'data/ir_config_parameter_data.xml',
        'views/product_template_concepts_views.xml',
        'views/product_template_subservice_views.xml',
        'views/product_template_accesories_views.xml',
    ],
    'auto_install': True,
    'application': False,
}
