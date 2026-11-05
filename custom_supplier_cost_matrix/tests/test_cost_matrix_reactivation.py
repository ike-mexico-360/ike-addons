# -*- coding: utf-8 -*-
"""Al confirmar una carga de matriz de costos, un registro inactivo que coincide
exactamente con la info importada debe reactivarse (no duplicarse); si la info importada
difiere, el inactivo se deja como está y se carga como registro nuevo."""

import base64
import csv
import io

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

CSV_HEADER = [
    'Subservicio', 'Entidad Federativa', 'Tipo de evento', 'Concepto', 'Categoría',
    'Tipo de incidente', 'Costo', 'Cuenta', 'Fecha festivo', 'Zona Geográfica',
    'Zona de alto riesgo', 'Activo convenio', 'Estado proveedor', 'Fecha inicio',
    'Fecha fin', 'Horario/Vacaciones', 'Kilometro inicial', 'Kilometro final',
    'Entidad origen', 'Municipio origen', 'Entidad destino', 'Municipio destino',
]


@tagged('post_install', '-at_install')
class TestSupplierCostMatrixReactivation(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # El lookup por nombre de "Entidad Federativa" filtra por el país de la compañía
        cls.env.company.write({'country_id': cls.env.ref('base.mx').id})

        cls.supplier = cls.env['res.partner'].create({
            'name': 'Proveedor DEV3838',
            'x_is_supplier': True,
        })
        cls.center = cls.supplier.x_supplier_center_ids[:1]

        cls.service = cls.env['product.category'].create({'name': 'Servicio DEV3838'})

        # Subservicio real, ya válido para get_subservices_domain()
        cls.subservice = cls.env.ref('custom_master_catalog.ike_product_product_vial_truck')

        cls.concept = cls.env['product.product'].create({
            'name': 'Concepto DEV3838',
            'type': 'service',
            'sale_ok': False,
            'sh_product_subscribe': False,
            'purchase_ok': True,
            'x_concept_ok': True,
            'categ_id': cls.env.ref('product.product_category_all').id,
            'list_price': 0,
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
        })

        cls.type_event = cls.env.ref('custom_master_catalog.custom_type_event_highway')
        cls.supplier_status = cls.env['custom.supplier.types.statuses'].create({'name': 'Vigente DEV3838'})
        cls.state = cls.env['res.country.state'].search([('country_id.code', '=', 'MX')], limit=1)
        cls.date_init = fields.Datetime.now()

    def setUp(self):
        super().setUp()
        self.upload = self.env['custom.supplier.upload.cost.matrix'].create({
            'supplier_center_id': self.center.id,
            'supplier_id': self.supplier.id,
            'service_id': self.service.id,
        })

    # === HELPERS ===
    def _staged_line_vals(self, cost, **extra):
        vals = {
            'supplier_upload_cost_matrix_id': self.upload.id,
            'subservice_id': self.subservice.id,
            'state_id': self.state.id,
            'type_event_id': self.type_event.id,
            'concept_id': self.concept.id,
            'supplier_status_id': self.supplier_status.id,
            'date_init': self.date_init,
            'cost': cost,
        }
        vals.update(extra)
        return vals

    def _matrix_line_vals(self, cost, active=True, **extra):
        vals = {
            'supplier_center_id': self.center.id,
            'subservice_id': self.subservice.id,
            'state_id': self.state.id,
            'type_event_id': self.type_event.id,
            'concept_id': self.concept.id,
            'supplier_status_id': self.supplier_status.id,
            'date_init': self.date_init,
            'cost': cost,
            'active': active,
        }
        vals.update(extra)
        return vals

    def _context_matrix_lines(self):
        """Todas las líneas (activas e inactivas) que comparten el contexto de los fixtures."""
        return self.env['custom.supplier.cost.matrix.line'].with_context(active_test=False).search([
            ('supplier_center_id', '=', self.center.id),
            ('subservice_id', '=', self.subservice.id),
            ('state_id', '=', self.state.id),
            ('type_event_id', '=', self.type_event.id),
            ('concept_id', '=', self.concept.id),
            ('supplier_status_id', '=', self.supplier_status.id),
            ('date_init', '=', self.date_init),
        ])

    def _build_csv_b64(self, row):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_HEADER)
        writer.writerow(row)
        return base64.b64encode(buffer.getvalue().encode('utf-8'))

    def _base_row(self, cost):
        row = [''] * len(CSV_HEADER)
        row[CSV_HEADER.index('Subservicio')] = self.subservice.name
        row[CSV_HEADER.index('Entidad Federativa')] = self.state.name
        row[CSV_HEADER.index('Tipo de evento')] = self.type_event.name
        row[CSV_HEADER.index('Concepto')] = self.concept.name
        row[CSV_HEADER.index('Costo')] = str(cost)
        row[CSV_HEADER.index('Estado proveedor')] = self.supplier_status.name
        row[CSV_HEADER.index('Fecha inicio')] = '2026-01-01'
        return row

    # === TESTS: lógica directa de _create_supplier_cost_matrix_lines ===

    def test_new_matrix_line_created_when_no_existing_match(self):
        line = self.env['custom.supplier.cost.product'].create(self._staged_line_vals(100.0))
        self.upload.action_confirm()

        records = self._context_matrix_lines()
        self.assertEqual(len(records), 1)
        self.assertTrue(records.active)
        self.assertEqual(records.cost, 100.0)
        self.assertFalse(line.not_confirm)

    def test_identical_active_record_discards_import_no_duplicate(self):
        existing = self.env['custom.supplier.cost.matrix.line'].create(self._matrix_line_vals(100.0, active=True))
        line = self.env['custom.supplier.cost.product'].create(self._staged_line_vals(100.0))

        self.upload.action_confirm()

        self.assertTrue(line.not_confirm)
        records = self._context_matrix_lines()
        self.assertEqual(len(records), 1)
        self.assertEqual(records.id, existing.id)
        self.assertTrue(records.active)

    def test_active_record_different_cost_archives_old_creates_new(self):
        existing = self.env['custom.supplier.cost.matrix.line'].create(self._matrix_line_vals(100.0, active=True))
        line = self.env['custom.supplier.cost.product'].create(self._staged_line_vals(150.0))

        self.upload.action_confirm()

        self.assertFalse(line.not_confirm)
        existing.invalidate_recordset()
        self.assertFalse(existing.active)

        records = self._context_matrix_lines()
        self.assertEqual(len(records), 2)
        active_records = records.filtered('active')
        self.assertEqual(len(active_records), 1)
        self.assertEqual(active_records.cost, 150.0)

    def test_inactive_record_identical_info_is_reactivated_not_duplicated(self):
        """Caso central"""
        existing = self.env['custom.supplier.cost.matrix.line'].create(self._matrix_line_vals(100.0, active=False))
        line = self.env['custom.supplier.cost.product'].create(self._staged_line_vals(100.0))

        self.upload.action_confirm()

        self.assertTrue(line.not_confirm, "La línea importada debe descartarse: ya existe la misma info (reactivada)")
        records = self._context_matrix_lines()
        self.assertEqual(len(records), 1, "No debe crearse un duplicado, solo reactivarse el existente")
        self.assertEqual(records.id, existing.id)
        self.assertTrue(records.active, "El registro inactivo debe reactivarse al tener info idéntica")

    def test_inactive_record_different_cost_loads_new_keeps_old_inactive(self):
        existing = self.env['custom.supplier.cost.matrix.line'].create(self._matrix_line_vals(100.0, active=False))
        line = self.env['custom.supplier.cost.product'].create(self._staged_line_vals(200.0))

        self.upload.action_confirm()

        self.assertFalse(line.not_confirm, "Info distinta/adicional: debe cargarse como registro nuevo")
        existing.invalidate_recordset()
        self.assertFalse(existing.active, "El inactivo no coincidente no debe tocarse")

        records = self._context_matrix_lines()
        self.assertEqual(len(records), 2)
        active_records = records.filtered('active')
        self.assertEqual(len(active_records), 1)
        self.assertEqual(active_records.cost, 200.0)
        self.assertEqual((records - active_records).id, existing.id)

    def test_active_mismatch_present_skips_inactive_reactivation(self):
        """Si ya hay un activo con costo distinto (se archiva), un inactivo idéntico en paralelo
        NO debe reactivarse de rebote: se sigue creando un registro nuevo."""
        active_rec = self.env['custom.supplier.cost.matrix.line'].create(self._matrix_line_vals(50.0, active=True))
        inactive_rec = self.env['custom.supplier.cost.matrix.line'].create(self._matrix_line_vals(100.0, active=False))
        line = self.env['custom.supplier.cost.product'].create(self._staged_line_vals(100.0))

        self.upload.action_confirm()

        active_rec.invalidate_recordset()
        inactive_rec.invalidate_recordset()
        self.assertFalse(active_rec.active, "El activo con costo distinto debe archivarse")
        self.assertFalse(inactive_rec.active, "El inactivo no debe reactivarse cuando ya hubo match activo")
        self.assertFalse(line.not_confirm)

        records = self._context_matrix_lines()
        self.assertEqual(len(records), 3)
        active_records = records.filtered('active')
        self.assertEqual(len(active_records), 1)
        self.assertEqual(active_records.cost, 100.0)
        self.assertNotEqual(active_records.id, inactive_rec.id)

    def test_duplicate_within_same_import_batch_keeps_only_one(self):
        line1 = self.env['custom.supplier.cost.product'].create(self._staged_line_vals(100.0))
        line2 = self.env['custom.supplier.cost.product'].create(self._staged_line_vals(100.0))

        self.upload.action_confirm()

        not_confirm_flags = (line1.not_confirm, line2.not_confirm)
        self.assertEqual(sum(not_confirm_flags), 1, "Exactamente una de las dos líneas duplicadas debe descartarse")
        records = self._context_matrix_lines()
        self.assertEqual(len(records), 1)

    def test_missing_required_field_raises_user_error(self):
        vals = self._staged_line_vals(100.0)
        vals['type_event_id'] = False
        self.env['custom.supplier.cost.product'].create(vals)

        with self.assertRaises(UserError):
            self.upload.action_confirm()

    # === TESTS: flujo completo vía archivo (acción real de carga) ===

    def test_full_csv_import_and_confirm_creates_matrix_line(self):
        upload = self.env['custom.supplier.upload.cost.matrix'].create({
            'supplier_center_id': self.center.id,
            'supplier_id': self.supplier.id,
            'service_id': self.service.id,
            'file': self._build_csv_b64(self._base_row(250.0)),
            'file_name': 'matriz_costos.csv',
            'file_type': 'text/csv',
        })
        upload.action_import_cost_matrix_file()

        self.assertEqual(len(upload.cost_product_ids), 1)
        self.assertFalse(upload.cost_product_ids.missing_value)

        upload.action_confirm()

        matrix_line = self.env['custom.supplier.cost.matrix.line'].search([
            ('supplier_upload_cost_matrix_id', '=', upload.id),
        ])
        self.assertEqual(len(matrix_line), 1)
        self.assertEqual(matrix_line.cost, 250.0)
        self.assertTrue(matrix_line.active)

    def test_second_file_upload_reactivates_manually_archived_line(self):
        """Simula el escenario real del ticket: se carga un archivo, luego el registro
        resultante se desactiva (manualmente o por otro proceso), y se vuelve a cargar
        el mismo archivo: no debe duplicarse, debe reactivarse."""
        upload1 = self.env['custom.supplier.upload.cost.matrix'].create({
            'supplier_center_id': self.center.id,
            'supplier_id': self.supplier.id,
            'service_id': self.service.id,
            'file': self._build_csv_b64(self._base_row(300.0)),
            'file_name': 'matriz_costos_1.csv',
            'file_type': 'text/csv',
        })
        upload1.action_import_cost_matrix_file()
        upload1.action_confirm()

        line1 = self.env['custom.supplier.cost.matrix.line'].search([
            ('supplier_upload_cost_matrix_id', '=', upload1.id),
        ])
        self.assertEqual(len(line1), 1)
        # El flujo de carga de archivo convierte "Fecha inicio" aplicando zona horaria, por lo
        # que el date_init resultante no es el mismo valor crudo que self.date_init: se captura
        # el real para poder buscar por el mismo contexto más abajo.
        key_domain = [
            ('supplier_center_id', '=', self.center.id),
            ('subservice_id', '=', self.subservice.id),
            ('state_id', '=', self.state.id),
            ('type_event_id', '=', self.type_event.id),
            ('concept_id', '=', self.concept.id),
            ('supplier_status_id', '=', self.supplier_status.id),
            ('date_init', '=', line1.date_init),
        ]
        line1.write({'active': False})

        upload2 = self.env['custom.supplier.upload.cost.matrix'].create({
            'supplier_center_id': self.center.id,
            'supplier_id': self.supplier.id,
            'service_id': self.service.id,
            'file': self._build_csv_b64(self._base_row(300.0)),
            'file_name': 'matriz_costos_2.csv',
            'file_type': 'text/csv',
        })
        upload2.action_import_cost_matrix_file()
        upload2.action_confirm()

        line1.invalidate_recordset()
        self.assertTrue(line1.active, "El registro archivado debe reactivarse al recibir la misma info")
        self.assertTrue(upload2.cost_product_ids.not_confirm)

        records = self.env['custom.supplier.cost.matrix.line'].with_context(active_test=False).search(key_domain)
        self.assertEqual(len(records), 1, "No debe existir un duplicado tras la segunda carga")
