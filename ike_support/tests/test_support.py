from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged('post_install', '-at_install')
class TestSupport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.support_user = new_test_user(cls.env, 'support_user', groups='ike_support.group_support_user')
        cls.support_manager = new_test_user(cls.env, 'support_manager', groups='ike_support.group_support_manager')
        cls.internal_user = new_test_user(cls.env, 'internal_user', groups='base.group_user')
        cls.failure = cls.env.ref('ike_support.support_failure_01')
        cls.platform = cls.env.ref('ike_support.support_platform_ike360')

    def _report(self, user):
        return self.env['ike.support.report'].with_user(user).create({
            'platform_id': self.platform.id, 'failure_id': self.failure.id, 'event': 'Inicio de sesión', 'description': 'No puedo entrar'})

    def test_report_sequence(self):
        first = self._report(self.support_user)
        second = self._report(self.support_user)
        self.assertRegex(first.name, r'^SOP\d{5}$')
        self.assertNotEqual(first.name, second.name)
        self.assertNotEqual(first.copy().name, first.name)

    def test_support_user_crud_reports(self):
        # El usuario de soporte edita los reportes de otros, pero no puede borrarlos
        own = self._report(self.support_user)
        other = self._report(self.support_manager).with_user(self.support_user)
        other.description = 'Editado por otro usuario de soporte'
        with self.assertRaises(AccessError):
            other.unlink()
        with self.assertRaises(AccessError):
            own.unlink()
        own.with_user(self.support_manager).unlink()

    def test_only_manager_can_change_state(self):
        report = self._report(self.support_user)
        with self.assertRaises(AccessError):
            report.write({'state': 'in_progress'})
        report.with_user(self.support_manager).write({'state': 'in_progress'})
        self.assertEqual(report.state, 'in_progress')

    def test_event_is_free_text(self):
        report = self._report(self.support_user)
        report.event = 'Al guardar un expediente'
        self.assertEqual(report.event, 'Al guardar un expediente')

    def test_platforms_preloaded(self):
        self.assertEqual(
            self.env['ike.support.platform'].search([]).mapped('name'),
            ['Ike360', 'Portal proveedores', 'Aplicación móvil proveedores'])

    def test_catalogs_only_editable_by_manager(self):
        for model, existing in (('ike.support.platform', self.platform), ('ike.support.failure', self.failure)):
            as_user = self.env[model].with_user(self.support_user)
            self.assertTrue(as_user.search_count([]))
            with self.assertRaises(AccessError):
                as_user.create({'name': 'Nueva opción'})
            with self.assertRaises(AccessError):
                existing.with_user(self.support_user).write({'name': 'Cambio'})
            record = self.env[model].with_user(self.support_manager).create({'name': 'Nueva opción'})
            record.write({'name': 'Nueva opción editada'})
            record.unlink()

    def test_isolated_from_other_users(self):
        report = self._report(self.support_user)
        for model in ('ike.support.report', 'ike.support.platform', 'ike.support.failure'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.internal_user).search([])
        with self.assertRaises(AccessError):
            report.with_user(self.internal_user).read(['name'])

        # search() no filtra menús por grupo; la visibilidad real la calcula _visible_menu_ids
        def visible(user):
            return self.env['ir.ui.menu'].with_user(user)._visible_menu_ids()

        root = self.env.ref('ike_support.menu_ike_support_root').id
        config = self.env.ref('ike_support.menu_ike_support_config').id
        self.assertNotIn(root, visible(self.internal_user))
        self.assertIn(root, visible(self.support_user))
        self.assertNotIn(config, visible(self.support_user))
        self.assertIn(config, visible(self.support_manager))

    def test_no_user_gets_groups_on_install(self):
        self.assertFalse(self.env.ref('base.user_admin').has_group('ike_support.group_support_user'))
