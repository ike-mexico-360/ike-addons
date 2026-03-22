# -*- coding: utf-8 -*-

{
    'name': "Ike Supplier Cost Matrix",
    'summary': """Supplier Cost Matrix for IKE""",
    'author': "AlsibaMx",
    'license': 'LGPL-3',
    'category': 'Uncategorized',
    'version': '18.0.1.0.0',
    'depends': [
        'custom_master_catalog',
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/custom_supplier_cost_product_schedule_data.xml",
        "views/custom_supplier_upload_cost_matrix_views.xml",
        "views/custom_supplier_cost_matrix_line_views.xml",
        "views/res_partner_suppler_center_views.xml",
        "views/res_partner_supplier_views.xml",
        "views/other/custom_supplier_cost_product_schedule_views.xml",
        "views/res_partner_menus.xml",
    ],
}
