{
    'name': 'IKE Soporte',
    'version': '18.0.1.0.0',
    'category': 'Services',
    'summary': 'Reportes de soporte (plataforma, falla, evento, descripción e imagen), aislados para el equipo de soporte.',
    'description': """
Módulo de soporte aislado.

- Reporte de soporte (ike.support.report) con folio automático (SOP00001),
  plataforma, falla, evento (texto libre), descripción e imagen.
- Catálogos de plataformas (ike.support.platform) y fallas (ike.support.failure),
  editables sólo por el administrador de soporte.
- Sólo los grupos propios del módulo (Usuario / Administrador de soporte) lo ven;
  ningún usuario recibe estos grupos al instalar: se asignan a mano.
""",
    'author': 'Galsiba',
    'license': 'LGPL-3',
    'icon': '/ike_support/static/description/icon.svg',
    'depends': ['base', 'mail'],
    'data': [
        'security/ike_support_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ike_support_catalog_data.xml',
        'views/ike_support_catalog_views.xml',
        'views/ike_support_report_views.xml',
        'views/ike_support_menus.xml',
    ],
    'installable': True,
    'application': True,
}
