{
    'name': 'Events Bright Pattern Direct Call',
    'version': '18.0.1.0.0',
    'category': 'Custom',
    'summary': 'Allow Bright Pattern Direct Call for Events directory',
    'description': """
        Enable Bright Pattern Direct Call for Events directory
    """,
    'author': 'AlsibaMX',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'ike_event',
    ],
    'data': [
        "views/res_config_settings_views.xml",
        "wizard/ike_phone_view_wizard_views.xml",
    ],
    'assets': {
        'web.assets_backend': [
            'ike_event_bp_direct_call/static/src/fields/bp_phone_dial/*.*',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
