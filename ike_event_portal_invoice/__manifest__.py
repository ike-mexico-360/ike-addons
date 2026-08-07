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
        'views/portal_invoice_templates.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
