from odoo.tests import Form, SingleTransactionCase, tagged
from odoo.tools.misc import file_open
import base64
import mimetypes
import logging

_logger = logging.getLogger("Tests")


@tagged('post_install', '-at_install')
class TestFileImport(SingleTransactionCase):

    def setUp(cls):
        super(TestFileImport, cls).setUp()
        # Crear usuario de prueba
        cls.user = cls.env.ref('base.user_admin')
        cls.supplier_center_id = cls.env['res.partner'].with_user(cls.user).create(dict(
            name='Test Center',
            type='center',
            disabled=False
        ))
        cls.supplier_id = cls.env['res.partner'].with_user(cls.user).create(dict(
            name='Test Supplier',
            x_is_supplier=True,
            disabled=False
        ))
        cls.service_id = cls.env['product.category'].search([('name', '=', 'Test Service')], limit=1)
        if not cls.service_id:
            cls.service_id = cls.env['product.category'].with_user(cls.user).create(dict(
                name='Test Service',
                disabled=False
            ))

        # Registros para crear la linea correcta en el detalle al importar del archivo
        cls.line_subservice_id = cls.env['product.product'].search([('name', '=', 'Test Line Subservice')], limit=1)
        if not cls.line_subservice_id:
            cls.line_subservice_id = cls.env['product.product'].with_user(cls.user).create(dict(
                name='Test Line Subservice',
                disabled=False
            ))
        cls.line_type_event_id = cls.env['custom.type.event'].search([('name', '=', 'Test Line Type Event')], limit=1)
        if not cls.line_type_event_id:
            cls.line_type_event_id = cls.env['custom.type.event'].with_user(cls.user).create(dict(
                name='Test Line Type Event',
                disabled=False
            ))
        cls.line_concept_id = cls.env['product.product'].search([('name', '=', 'Test Line Concept')], limit=1)
        if not cls.line_concept_id:
            cls.line_concept_id = cls.env['product.product'].with_user(cls.user).create(dict(
                name='Test Line Concept',
                disabled=False
            ))
        cls.line_vehicle_category_id = cls.env['fleet.vehicle.model.category'].search([('name', '=', 'Test Line Vehicle Category')], limit=1)
        if not cls.line_vehicle_category_id:
            cls.line_vehicle_category_id = cls.env['fleet.vehicle.model.category'].with_user(cls.user).create(dict(
                name='Test Line Vehicle Category',
                disabled=False
            ))
        cls.line_account_id = cls.env['res.partner'].search([('name', '=', 'Test Line Account')], limit=1)
        if not cls.line_account_id:
            cls.line_account_id = cls.env['res.partner'].with_user(cls.user).create(dict(
                name='Test Line Account',
                x_is_account=True,
                disabled=False
            ))
        cls.line_supplier_status_id = cls.env['custom.supplier.types.statuses'].search([('name', '=', 'Test Line Supplier Status')], limit=1)
        if not cls.line_supplier_status_id:
            cls.line_supplier_status_id = cls.env['custom.supplier.types.statuses'].with_user(cls.user).create(dict(
                name='Test Line Supplier Status',
                disabled=False
            ))

        # ===== XLSX =====
        cls.xlsx_file_name = 'file.xlsx'
        with file_open('custom_master_catalog/tests/supplier_upload_cost_matrix_files/' + cls.xlsx_file_name, 'rb') as f:
            xlsx_file = base64.encodebytes(f.read())
            mimetype, _ = mimetypes.guess_type(cls.xlsx_file_name)
            file_type = mimetype or 'application/octet-stream'
            cls.import_xlsx = cls.env["custom.supplier.upload.cost.matrix"].with_user(cls.user).create({
                'file': xlsx_file,
                'file_name': cls.xlsx_file_name,
                'file_type': file_type,
                'supplier_center_id': cls.supplier_center_id.id,
                'supplier_id': cls.supplier_id.id,
                'service_id': cls.service_id.id,
            })

        # ===== CSV =====
        cls.csv_file_name = 'file.csv'
        with file_open('custom_master_catalog/tests/supplier_upload_cost_matrix_files/' + cls.csv_file_name, 'rb') as f:
            csv_file = base64.encodebytes(f.read())
            mimetype, _ = mimetypes.guess_type(cls.csv_file_name)
            file_type = mimetype or 'application/octet-stream'
            cls.import_csv = cls.env["custom.supplier.upload.cost.matrix"].with_user(cls.user).create({
                'file': csv_file,
                'file_name': cls.csv_file_name,
                'file_type': file_type,
                'supplier_center_id': cls.supplier_center_id.id,
                'supplier_id': cls.supplier_id.id,
                'service_id': cls.service_id.id,
            })

        # FORM
        cls.form_view_id = cls.env.ref('custom_master_catalog.custom_supplier_upload_cost_matrix_view_form')

    def test_file_upload_xlsx(self):
        """Test para verificar la carga exitosa de un archivo xlsx válido"""
        with Form(record=self.import_xlsx, view=self.form_view_id) as f:
            self.assertEqual(f.file_name, self.xlsx_file_name)
            self.assertEqual(f.file_type, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def test_file_upload_csv(self):
        """Test para verificar la carga exitosa de un archivo csv válido"""
        with Form(record=self.import_csv, view=self.form_view_id) as f:
            self.assertEqual(f.file_name, self.csv_file_name)
            self.assertEqual(f.file_type, 'text/csv')

    def test_execute_import_process_xlsx(self):
        """Test para verificar importacion xlsx"""
        country_id = self.env.ref('base.mx').id
        self.import_xlsx.action_import_cost_matrix_file()
        self.assertEqual(self.import_xlsx.product_ids_count, 1)
        _logger.warning(self.import_xlsx.cost_product_ids_with_missing_values)
        for product in self.import_xlsx.cost_product_ids:
            required_fields = ['subservice_id', 'state_id', 'type_event_id', 'vehicle_category_id', 'cost', 'date_init']
            # Comprueba que los campos requeridos tienen valor
            for field in required_fields:
                self.assertNotEqual(product[field].id, False, "{} no encontrado".format(field))
            # Comprueba que el país es México
            self.assertEqual(product.country_id.id, country_id, "País no coincide")
            # Comprobar que el estado es de México
            self.assertEqual(product.state_id.country_id.id, country_id, "Estado no pertenece al país")

    def test_execute_import_process_csv(self):
        """Test para verificar importacion csv"""
        self.import_csv.action_import_cost_matrix_file()
        self.assertEqual(self.import_csv.product_ids_count, 1)

    # def test_imported_records_by_xlsx(self):
    #     """Test para verificar importación de registros por xlsx"""
    #     # Verificar que se creó el registro
    #     self.assertEqual(self.import_xlsx.product_ids_count, 1)

    # def test_imported_records_by_csv(self):
    #     """Test para verificar importación de registros por csv"""
    #     # Verificar que se creó el registro
    #     self.assertEqual(self.import_csv.product_ids_count, 1)

    # def test_04_file_upload_wrong_encoding(self):
    #     """Test para verificar el manejo de archivos con codificación incorrecta"""
    #     # Crear contenido con codificación incorrecta (no UTF-8)
    #     wrong_encoding_content = base64.b64encode('ñáéíóú'.encode('latin-1'))

    #     # Ejecutar el método con codificación incorrecta
    #     with patch('odoo.addons.tu_modulo.models.tu_modelo.logger') as mock_logger:
    #         result = self.TestModel.with_user(self.user).action_import_cost_matrix_file(wrong_encoding_content)

    #         # Verificar que se registró un error
    #         mock_logger.error.assert_called()

    #         # Verificar que hay mensaje de error
    #         self.assertTrue(result.get('error', False))

    # @mute_logger('odoo.addons.tu_modulo.models.tu_modelo')
    # def test_05_action_import_cost_matrix_file_exception_handling(self):
    #     """Test para verificar el manejo de excepciones durante el procesamiento"""
    #     # Crear datos CSV válidos
    #     csv_data = [['name', 'email'], ['Test', 'test@example.com']]
    #     output = io.StringIO()
    #     writer = csv.writer(output)
    #     writer.writerows(csv_data)
    #     csv_content = output.getvalue().encode('utf-8')
    #     encoded_content = base64.b64encode(csv_content)

    #     # Forzar una excepción durante el procesamiento
    #     with patch.object(self.TestModel, '_process_csv_data', side_effect=Exception('Error de procesamiento')):
    #         result = self.TestModel.with_user(self.user).action_import_cost_matrix_file(encoded_content)

    #         # Verificar que hay mensaje de error
    #         self.assertTrue(result.get('error', False))
    #         self.assertIn('Error de procesamiento', result.get('error_message', ''))

    # def test_06_access_rights(self):
    #     """Test para verificar los controles de acceso"""
    #     # Crear usuario sin permisos
    #     user_without_access = self.env.ref('base.user_demo')

    #     # Intentar ejecutar el método sin permisos
    #     with self.assertRaises(Exception):
    #         self.TestModel.with_user(user_without_access).action_import_cost_matrix_file(b'')
