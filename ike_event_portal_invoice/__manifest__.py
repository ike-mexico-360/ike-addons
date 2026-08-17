{
    'name': 'Ike Events Portal - Invoice',
    'version': '18.0.1.0.0',
    'summary': 'Portal section for DIAN electronic invoicing documents',
    'description': '',
    'author': '',
    'website': '',
    'license': 'LGPL-3',
    'category': 'Technical',
    'depends': [
        'portal', 'account', 'ike_event_portal',
    ],
    'data': [
        'report/report_invoice.xml',
        'security/ir.model.access.csv',
        'views/portal_invoice_templates.xml',
        'views/portal_purchase_templates.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
