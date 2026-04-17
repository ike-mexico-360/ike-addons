# -*- coding: utf-8 -*-

# import re
import base64
# import json
import pytz
import logging
import mimetypes
import datetime

from collections import defaultdict
from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


REQUIRED_LINE_FIELDS = [
    'subservice_id',
    'state_id',
    'type_event_id',
    'concept_id',
    # 'vehicle_category_id',
    'cost',
    'supplier_status_id',
    'date_init'
]


class CustomSupplierUploadCostMatrix(models.Model):
    _name = 'custom.supplier.upload.cost.matrix'
    _description = 'Supplier Upload Cost Matrix'
    _inherit = ['mail.thread']
    _rec_name = 'supplier_center_id'

    FILE_TYPES = {
        'csv': 'text/csv',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }

    supplier_center_id = fields.Many2one(
        comodel_name='res.partner', string='Center of attention',
        domain=[
            ('parent_id.x_is_supplier', '=', True),
            ('type', '=', 'center'),
            ('disabled', '=', False)
        ], ondelete='restrict', tracking=True)

    supplier_id = fields.Many2one(
        comodel_name='res.partner', string='Supplier',
        domain=[
            ('x_is_supplier', '=', True),
            ('disabled', '=', False)
        ], ondelete='restrict', tracking=True)

    active = fields.Boolean(default=True)
    service_id = fields.Many2one(
        comodel_name='product.category', string='Service',
        domain=[('disabled', '=', False)], tracking=True)
    service_domain = fields.Binary(string='Service Domain', compute='_compute_service_domain')
    state = fields.Selection(
        [("draft", "Draft"), ("confirmed", "Confirmed"), ("refused", "Refused")],
        default='draft', string="Header state", tracking=True)
    # FILE
    date_upload = fields.Datetime(string='Date upload', tracking=True)
    date_confirm = fields.Datetime(string='Date confirm', tracking=True)
    file = fields.Binary(string='File')
    file_name = fields.Char(string='File Name', tracking=True)
    file_type = fields.Char('File Type')

    # DETAILS
    cost_product_ids = fields.One2many(
        comodel_name='custom.supplier.cost.product',
        inverse_name='supplier_upload_cost_matrix_id',
        string='Product cost', tracking=True)
    product_ids_count = fields.Integer(compute='_compute_product_ids_count')
    products_to_confirm_count = fields.Integer(compute='_compute_products_to_confirm_count')
    product_ids_with_missing_values_count = fields.Integer(compute='_compute_product_ids_with_missing_values_count')

    # === ONCHANGE === #
    @api.onchange("supplier_center_id")
    def _onchange_supplier_id(self):
        """Set fields from supplier_center_id."""
        if self.supplier_center_id and self.supplier_center_id.parent_id:
            self.supplier_id = self.supplier_center_id.parent_id.id

    @api.onchange('file')
    def _onchange_file(self):
        if self.file and self.file_name:
            mimetype, _ = mimetypes.guess_type(self.file_name)
            self.file_type = mimetype or 'application/octet-stream'

    # === COMPUTE === #
    @api.depends('cost_product_ids')
    def _compute_product_ids_count(self):
        for rec in self:
            rec.product_ids_count = len(rec.cost_product_ids)

    @api.depends('cost_product_ids', 'cost_product_ids.not_confirm')
    def _compute_products_to_confirm_count(self):
        for rec in self:
            rec.products_to_confirm_count = len(rec.cost_product_ids.filtered(lambda x: x.not_confirm is False))

    @api.depends('cost_product_ids', 'cost_product_ids.missing_value')
    def _compute_product_ids_with_missing_values_count(self):
        for rec in self:
            rec.product_ids_with_missing_values_count = len(rec.cost_product_ids.filtered(lambda x: x.missing_value is True))

    @api.depends('supplier_center_id')
    def _compute_service_domain(self):
        for rec in self:
            rec.service_domain = [
                ('id', 'not in', [
                    self.env.ref('product.product_category_all').id,
                    self.env.ref('product.product_category_1').id,
                    self.env.ref('product.cat_expense').id
                ])
            ]

    # === ACTION === #
    def action_import_cost_matrix_file(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("No se ha cargado ningún archivo."))
        if self.file_type not in self.FILE_TYPES.values():
            raise UserError(_(f"El archivo debe ser tipo {', '.join(self.FILE_TYPES.keys())}"))

        MATCH_FIELDS = {
            'Subservicio': {
                'name': 'subservice_id', 'required': True,
                'domain': self.env['product.product'].get_subservices_domain() + [('disabled', '=', False)]
            },
            'Entidad Federativa': {
                'name': 'state_id', 'required': False,
                'domain': [('disabled', '=', False), ('country_id', '=', self.env.company.country_id.id)]
            },
            'Tipo de evento': {
                'name': 'type_event_id', 'required': True, 'domain': [('disabled', '=', False)]
            },
            'Concepto': {
                'name': 'concept_id', 'required': True,
                'domain': self.env['product.product'].get_concepts_domain() + [('disabled', '=', False)]
            },
            # * Cambia 'vehicle_category_id' por 'subservice_specification_id'
            'Categoría': {
                'name': 'subservice_specification_id', 'required': False, 'domain': [('disabled', '=', False)]
            },
            'Costo': {
                'name': 'cost', 'required': True, 'domain': False
            },
            'Cuenta': {
                'name': 'account_id', 'required': False, 'domain': [('disabled', '=', False), ('x_is_account', '=', True)]
            },
            'Fecha festivo': {
                'name': 'holiday_date_applies', 'required': False, 'domain': False
            },
            'Zona Geográfica': {
                'name': 'geographical_area_id', 'required': False, 'domain': [('disabled', '=', False)]
            },
            'Activo convenio': {
                'name': 'active_agreement', 'required': False, 'domain': False
            },
            'Estado proveedor': {
                'name': 'supplier_status_id', 'required': True, 'domain': [('disabled', '=', False)]
            },
            'Fecha inicio': {
                'name': 'date_init', 'required': True, 'domain': False
            },
            'Fecha fin': {
                'name': 'date_end', 'required': False, 'domain': False
            },
            'Horario/Vacaciones': {
                'name': 'vacation_schedule_ids', 'required': False, 'domain': [('disabled', '=', False)]
            }
        }

        # Read File
        rows, rows_count, uploaded_file, file_size = self._read_file(self.file, self.file_name, self.file_type)
        # Validate File Data
        all_columns = MATCH_FIELDS.keys()
        required_columns = [col for col, cfg in MATCH_FIELDS.items() if cfg['required']]
        self._validate_columns(header=rows[0], required_columns=required_columns)
        # Get File Records
        records_data: list[dict] = self._convert_import_data_to_json(rows, all_columns)
        _logger.info("Iniciando importacion de %s con %d registros", self.file_name, len(records_data))
        normalized_data, missing_required_fields = self._normalize_data(records_data, MATCH_FIELDS)
        self._save_processed_data(normalized_data)
        self.date_upload = fields.Datetime.now()
        _logger.info("Finalizando importacion de %s con %d registros", self.file_name, len(normalized_data))
        # Necesario para validar requeridos visualmente al importar
        self.cost_product_ids._onchange_required_fields()
        return True

    def action_confirm(self):
        for rec in self:
            rec._create_supplier_cost_matrix_lines()
            rec.write({'date_confirm': fields.Datetime.now(), 'state': 'confirmed'})

    def _action_decline(self, reason: str):
        if reason:
            body = Markup("""
                <ul class="mb-0 ps-4">
                    <li>
                        <span class="o-mail-Message-trackingOld me-1 px-1 text-muted fw-bold">{}</span>
                        <i class='o-mail-Message-trackingSeparator fa fa-long-arrow-right mx-1 text-600'/>
                        <span class="o-mail-Message-trackingNew me-1 fw-bold text-info">{}</span>
                        <span class="o-mail-Message-trackingField ms-1 fst-italic text-muted">({})</span>
                    </li>
                </ul>
            """).format(
                _('Reason for decline'),
                reason,
                _('Decline')
            )
            self.message_post(
                body=body,
                message_type='notification',
                body_is_html=True)
        self.cost_product_ids.unlink()
        self.file = False
        self.file_name = False
        self.file_type = False
        self.state = 'refused'

    def action_decline(self):
        self.ensure_one()
        return {
            'name': _('Reason for decline'),
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'custom.model.confirm.wizard',
            'views': [(None, 'form')],
            'target': 'new',
            'context': {
                'default_res_model': self._name,
                'default_res_ids': str([self.id]),
                'default_action_name': '_action_decline',
                'is_reject': True,
            }
        }

    # === ACTION VIEW === #
    def view_records_with_missing_values(self):
        self.ensure_one()
        view_id = self.env.ref('custom_supplier_cost_matrix.custom_supplier_upload_cost_lines_popup_view_tree').id
        return {
            'name': _('Records with required missing Values'),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.supplier.cost.product',
            'view_mode': 'list',
            'target': 'new',
            'context': {
                'default_supplier_upload_cost_matrix_id': self.id,
                'search_default_filter_enabled': 1,
                'dialog_size': 'large',
            },
            'view_id': view_id,
            'domain': [('supplier_upload_cost_matrix_id', '=', self.id), ('missing_value', '=', True)],
            'views': [(False, 'list')],
        }

    # === FILE PRIVATE METHODS === #
    def _read_file(self, file, file_name, file_type):
        """ Leer los datos del archivo """
        # Decodificar el archivo
        options = {
            'encoding': '',
            'separator': '',
            'quoting': '"',
            'date_format': '',
            'datetime_format': '',
            'float_thousand_separator': ',',
            'float_decimal_separator': '.',
            'advanced': True,
            'has_headers': True,
            'keep_matches': False,
            'sheets': [],
            'sheet': ''
        }
        base_import = self.env['base_import.import'].create({
            'file_name': file_name,
            'file_type': file_type,
        })
        file_data = base64.b64decode(file)
        file_size = len(file_data)
        base_import.file = file_data
        rows_count, rows = base_import._read_file(options)  # noqa: F841  # pylint: disable=W0612
        return rows, rows_count, file_data, file_size

    def _validate_columns(self, header, required_columns):
        """ Validar columnas requeridas en el archivo de importación """
        # Leer los encabezados
        # Validar columnas requeridas
        missing_columns = [col for col in required_columns if col not in header]
        if missing_columns:
            raise UserError(f"Faltan las siguientes columnas requeridas: {', '.join(missing_columns)}")

    # Convertir la información a formato DICT
    def _convert_import_data_to_json(self, rows, columns) -> list[dict]:
        """ Convertir datos de importación al estilo JSON esperado """
        header = rows[0]
        # Obtener columnas requeridas
        column_idx = {col: idx for idx, col in enumerate(header) if col in columns}
        if not column_idx:
            raise ValueError("Ninguna de las columnas requeridas está presente en el archivo.")
        records = [
            {col_name: row[col_id] for col_name, col_id in column_idx.items()}
            for row in rows[1:]  # Ignorar la fila de encabezados
        ]
        return records

    # Normalizar la información a datos compatibles con Odoo, como los campos m2o
    def _normalize_data(self, records_data, match_fields):
        """ Normalizar datos, convertir nombres del excel a su correspondiente en Odoo, obtener valores de campos m2o. """
        if not len(records_data):
            return [], []

        def _validate_required_fields(match_fields, rec):
            for field, value in rec.items():
                required = match_fields[field]['required']
                if required is True and not value:
                    return False
            return True

        def attach_hours(field, date):
            if not date:
                return False

            if isinstance(date, datetime.date):
                if field == 'date_init':
                    date = datetime.datetime.combine(date, datetime.time(0, 0, 0))
                elif field == 'date_end':
                    date = datetime.datetime.combine(date, datetime.time(23, 59, 59))

            # Convertir a la zona horaria del usuario y luego a UTC
            if isinstance(date, datetime.datetime):
                # Obtener la zona horaria del contexto/usuario
                tz_name = self.env.context.get('tz') or self.env.user.tz
                if not tz_name:
                    tz_name = 'UTC'
                # Asignar la zona horaria local al datetime naive
                local_tz = pytz.timezone(tz_name)
                date_local = local_tz.localize(date)
                # Convertir a UTC
                date_utc = date_local.astimezone(pytz.UTC)
                # Quitar la info de timezone para Odoo
                date = date_utc.replace(tzinfo=None)
            _logger.debug("%s: %s", field, date)
            return date

        def _normalize_field(field_data, value, domain, required, stored_values, rec_data=None):
            if not domain:
                domain = []
            if not value:
                return False, False
            missing_value = False
            aux_value = str(value).strip() if value else ''
            # * m2o field =========================================================================
            if field_data['ttype'] == 'many2one':
                field_name = field_data['name']
                if field_name not in stored_values:
                    stored_values[field_name] = {}
                if aux_value not in stored_values[field_name]:
                    # FIXED: Dominio contextual para geographical_area_id, necesario para filtrar por state_id
                    # derivado de que las zonas geográficas se llaman igual en distintos estados
                    search_domain = domain[:]
                    if field_name == 'geographical_area_id' and rec_data and rec_data.get('state_id'):
                        search_domain += [('state_id', '=', rec_data['state_id'])]

                    record_domain = search_domain + [('name', '=', aux_value)]
                    record = self.env[field_data['relation']].search_read(record_domain, ['id'])
                    if record:
                        value = record[0]['id']
                        stored_values[field_name][aux_value] = value
                    else:
                        value = False
                        missing_value = True
                        stored_values[field_name][aux_value] = value
                else:
                    value = stored_values[field_name][aux_value]
            # * m2m field =========================================================================
            elif field_data['ttype'] == 'many2many':
                field_name = field_data['name']
                values = [v.strip() for v in value.split(',')]  # Separamos cada valor por coma y eliminamos espacios
                field_values = []  # Para devolver lista de ids
                if field_name not in stored_values:
                    stored_values[field_name] = {}
                for val in values:
                    aux_val = val
                    if aux_val not in stored_values[field_name]:
                        record_domain = domain + [('name', '=', aux_val)]
                        record = self.env[field_data['relation']].search_read(record_domain, ['id'])
                        if record:
                            val_id = record[0]['id']
                            stored_values[field_name][aux_val] = val_id
                            field_values.append(val_id)
                        else:
                            val_id = False
                            missing_value = True
                            stored_values[field_name][aux_val] = val_id
                    else:
                        if stored_values[field_name][aux_val] is not False:
                            field_values.append(stored_values[field_name][aux_val])
                return field_values, missing_value
            # * float field =========================================================================
            elif field_data['ttype'] == 'float':
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    _logger.error("No se pudo convertir '%s' a float para campo %s", value, field_data['name'])
                    missing_value = True
                    value = 0.0
            # * integer field =========================================================================
            elif field_data['ttype'] == 'integer':
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    _logger.error("No se pudo convertir '%s' a int para campo %s", value, field_data['name'])
                    missing_value = True
                    value = 0
            # * boolean field =========================================================================
            elif field_data['ttype'] == 'boolean':
                if isinstance(value, str):
                    if value.lower() in ('sí', 'si', 'yes', 'true'):
                        value = True
                    else:
                        value = False
                value = bool(value)
            # * date field =========================================================================
            elif field_data['ttype'] == 'date':
                try:
                    value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        value = datetime.datetime.strptime(value, '%d-%m-%Y').date()
                    except ValueError:
                        try:
                            value = datetime.datetime.strptime(value, '%d/%m/%Y').date()
                        except ValueError:
                            _logger.error("Formato de fecha no reconocido: '%s' para campo %s", value, field_data['name'])
                            missing_value = True
                            value = False
            # * datetime field =========================================================================
            elif field_data['ttype'] == 'datetime':  # ! Importante: Se tratará como Date, ya que en el excel debe venir solo fecha  # noqa: E501
                try:
                    value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        value = datetime.datetime.strptime(value, '%d-%m-%Y').date()
                    except ValueError:
                        try:
                            value = datetime.datetime.strptime(value, '%d/%m/%Y').date()
                        except ValueError:
                            _logger.error("Formato de fecha no reconocido: '%s' para campo %s", value, field_data['name'])
                            missing_value = True
                            value = False
            if required and not value:
                missing_value = True
            return value, missing_value

        def _normalize_value_for_log(field_data, value):
            if field_data['ttype'] == 'float':
                value = float(value)
            elif field_data['ttype'] == 'integer':
                value = int(value)
            elif field_data['ttype'] == 'boolean':
                if isinstance(value, str):
                    if value.lower() in ('sí', 'si', 'yes', 'true'):
                        value = True
                    else:
                        value = False
                value = bool(value)
            return value

        field_names = [x['name'] for x in match_fields.values()]
        model_fields = self.env['ir.model.fields'].search_read([
            ('model', '=', 'custom.supplier.cost.product'),
            ('name', 'in', field_names),
        ], ['name', 'field_description', 'ttype', 'relation'])
        fields_hashmap = {field['name']: field for field in model_fields}

        normalized_records = []
        missing_fields_records = []
        stored_values = {x['name']: {} for x in model_fields if x['relation']}

        for rec in records_data:
            is_valid = _validate_required_fields(match_fields, rec)
            if not is_valid:
                missing_fields_records.append(rec)
                continue

            missing_values_json = {}

            # FIX: Procesar state_id PRIMERO
            priority_fields = ['Entidad Federativa']  # state_id debe ir primero
            ordered_fields = [f for f in priority_fields if f in rec] + [f for f in rec if f not in priority_fields]

            # data = {'supplier_upload_cost_matrix_id': self.id}
            rec_data = {'supplier_upload_cost_matrix_id': self.id}  # FIX: Contexto para geographical_area_id
            for file_field in ordered_fields:
                missing_value = False
                odoo_field = match_fields[file_field]['name']
                field_domain = match_fields[file_field]['domain']
                field_required = match_fields[file_field]['required']
                field_data = fields_hashmap[odoo_field]
                value = rec[file_field]

                # FIX: Pasar rec_normalized con state_id ya resuelto
                normalized_value, missing_value = _normalize_field(
                    field_data, value, field_domain, field_required, stored_values, rec_data=rec_data)

                if odoo_field in ('date_init', 'date_end'):
                    normalized_value = attach_hours(odoo_field, normalized_value)
                # data[odoo_field] = normalized_value
                rec_data[odoo_field] = normalized_value  # Acumular para siguientes campos

                if missing_value:
                    missing_values_json[odoo_field] = _normalize_value_for_log(field_data, value)

            # Manejador de campos faltantes
            if missing_values_json:
                str_missing_values = """{\n\n"""
                for field, value in missing_values_json.items():
                    field_data = fields_hashmap[field]
                    str_missing_values += """    # %s\n    %s = '%s'\n\n""" % (field_data['field_description'], field, value)
                str_missing_values += "}"
                rec_data.update({
                    'missing_value': True,
                    'missing_values': str_missing_values
                })
            normalized_records.append(rec_data)
        return normalized_records, missing_fields_records

    # Guardar la información procesada
    def _save_processed_data(self, normalized_data):
        if normalized_data:
            self.env['custom.supplier.cost.product'].create(normalized_data)

    # === CONFIRM PRIVATE METH0DS === #
    def _create_supplier_cost_matrix_lines(self):
        # Validar campos requeridos antes de guardar
        required_fields = REQUIRED_LINE_FIELDS
        consider_duplicate_fields = required_fields + [
            'account_id', 'geographical_area_id', 'holiday_date_applies', 'active_agreement', 'date_end',
            'vacation_schedule_ids', 'subservice_specification_id'
        ]
        lines_to_import = defaultdict(list)

        # Función helper para normalizar valores
        def normalize_value(val):
            """Normaliza valores para comparación"""
            if isinstance(val, tuple) and len(val) == 2:
                return val[0]  # Many2one: extraer ID
            elif isinstance(val, list):
                return tuple(sorted(val))  # Many2many: convertir lista a tupla ordenada
            return val

        key_fields = [f for f in consider_duplicate_fields if f != 'cost']

        for line in self.cost_product_ids:
            to_check_duplicate_data = line.read(consider_duplicate_fields)
            if to_check_duplicate_data:
                to_check_duplicate_data = to_check_duplicate_data[0]
                line_data = {k: v for k, v in to_check_duplicate_data.items() if k in required_fields}
                if not all(list(line_data.values())):
                    raise UserError(_("Missing required fields, please review the lines marked in red."))
                aux_line_data = to_check_duplicate_data.copy()
                # Normalizar valores antes de crear la clave
                record_key = tuple(normalize_value(aux_line_data[f]) for f in key_fields if f in aux_line_data)
                lines_to_import[record_key].append(to_check_duplicate_data)

        # Validar por duplicados, si hay, desactivar el existente y crear el nuevo
        exist_records = self.env['custom.supplier.cost.matrix.line'].search_read([
            ('supplier_center_id', '=', self.supplier_center_id.id),
            ('active', '=', True),
        ], consider_duplicate_fields)

        odoo_data = defaultdict(list)
        for rec in exist_records:
            aux_rec = rec.copy()
            # Normalizar valores antes de crear la clave
            odoo_record_key = tuple(normalize_value(aux_rec[f]) for f in key_fields if f in aux_rec)
            odoo_data[odoo_record_key].append(rec)

        # Manejo de duplicados importados y existentes
        for import_key, import_lines in lines_to_import.items():
            if not import_lines:
                continue

            # Duplicados importados: marcar todos menos el primero
            if len(import_lines) > 1:
                dup_ids = [x['id'] for x in import_lines[1:]]
                self.env['custom.supplier.cost.product'].sudo().browse(dup_ids).write({'not_confirm': True})
                _logger.warning("[IMPORT] %d duplicados descartados para %s", len(import_lines) - 1, import_key)
                line = import_lines[0]
            else:
                line = import_lines[0]

            # Buscar si existe un registro con el mismo contexto
            if import_key in odoo_data:
                existing_records = odoo_data[import_key]
                importing_cost = normalize_value(line['cost'])

                is_identical = False
                to_archive = []

                for existing_rec in existing_records:
                    existing_cost = normalize_value(existing_rec['cost'])

                    if importing_cost == existing_cost:
                        # Registro IDÉNTICO (mismo costo): descartar el importado
                        is_identical = True
                        _logger.info(
                            "[SKIP] Registro idéntico (cost=%s, ID %s), descartando importado ID %s",
                            existing_cost, existing_rec['id'], line['id'])
                        self.env['custom.supplier.cost.product'].sudo().browse([line['id']]).write({'not_confirm': True})
                        break
                    else:
                        # Mismo contexto pero COSTO DIFERENTE: marcar para archivar
                        to_archive.append(existing_rec['id'])
                        _logger.warning(
                            "[UPDATE] Marcando para archivar ID %s (cost: %s -> %s)",
                            existing_rec['id'], existing_cost, importing_cost)

                # Archivar todos los registros con costo diferente
                if not is_identical and len(to_archive) > 0:
                    self.env['custom.supplier.cost.matrix.line'].sudo().browse(to_archive).write({
                        'active': False
                    })
                    _logger.info("[UPDATE] %d registro(s) archivado(s)", len(to_archive))

        # Guardar solo las líneas confirmadas
        to_confirm = self.cost_product_ids.filtered(lambda x: not x.not_confirm)
        vals_to_create = []
        for line in to_confirm:
            vals = self._get_values_supplier_cost_matrix_line(line)
            vals_to_create.append(vals)
        if len(vals_to_create) > 0:
            self.env['custom.supplier.cost.matrix.line'].sudo().create(vals_to_create)
        _logger.info("[CONFIRM] Confirmed %s records", len(vals_to_create))

    def _get_values_supplier_cost_matrix_line(self, line):
        vals = {
            "supplier_upload_cost_matrix_id": self.id,
            "custom_supplier_cost_product_id": line.id,
            "supplier_center_id": self.supplier_center_id.id,
            "subservice_id": line.subservice_id.id,
            "state_id": line.state_id.id if line.state_id else False,
            "geographical_area_id": line.geographical_area_id.id if line.geographical_area_id else False,  # FIX
            "type_event_id": line.type_event_id.id,
            "concept_id": line.concept_id.id,
            "subservice_specification_id": line.subservice_specification_id.id if line.subservice_specification_id else False,
            # "vehicle_category_id": line.vehicle_category_id.id if line.vehicle_category_id else False,
            "account_id": line.account_id.id if line.account_id else False,  # FIX
            "cost": line.cost,
            "holiday_date_applies": line.holiday_date_applies,
            "active_agreement": line.active_agreement,
            "supplier_status_id": line.supplier_status_id.id,
            "date_init": line.date_init,
            "date_end": line.date_end,
            "vacation_schedule_ids": [(6, 0, line.vacation_schedule_ids.ids)],
        }
        return vals


class CustomSupplierCostProduct(models.Model):
    _name = 'custom.supplier.cost.product'
    _description = 'Supplier Cost Product'
    _rec_name = 'subservice_id'

    active = fields.Boolean(default=True)
    supplier_upload_cost_matrix_id = fields.Many2one(
        "custom.supplier.upload.cost.matrix", string='Supplier Cost Matrix', ondelete='cascade')
    service_id = fields.Many2one(
        related='supplier_upload_cost_matrix_id.service_id', string='Service', sub_tracking=True, ondelete='restrict')
    subservice_id = fields.Many2one('product.product', string='Subservice', sub_tracking=True, ondelete='restrict')

    country_id = fields.Many2one("res.country", string="Country", default=lambda self: self.env.company.country_id)
    state_id = fields.Many2one('res.country.state', string='State', sub_tracking=True)
    geographical_area_id = fields.Many2one(
        'custom.state.municipality', string='Geographical area', sub_tracking=True, ondelete='restrict')

    type_event_id = fields.Many2one('custom.type.event', string='Event type', sub_tracking=True, ondelete='restrict')
    mapping_product_ids = fields.One2many(
        comodel_name='product.product', string='Mapping products',
        compute='_compute_mapping_product_ids')
    concept_id = fields.Many2one(
        comodel_name='product.product', string='Concept', sub_tracking=True, ondelete='restrict')
    subservice_specification_id = fields.Many2one(
        'custom.subservice.specification', string='Subservice Specification', tracking=True, index=True)
    # ToDo: Remove vehicle_category_id
    vehicle_category_id = fields.Many2one(
        'fleet.vehicle.model.category', string='Category', sub_tracking=True, ondelete='restrict')
    account_id = fields.Many2one(
        comodel_name='res.partner',
        string='Account',
        domain=[('x_is_account', '=', True)],
        sub_tracking=True, ondelete='restrict')

    cost = fields.Float(string='Cost', sub_tracking=True)
    holiday_date_applies = fields.Boolean(string="Holiday date applies", sub_tracking=True)
    high_risk_area = fields.Boolean(related="geographical_area_id.red_zone", string="High risk area", sub_tracking=True)
    active_agreement = fields.Boolean(string="Active agreement", sub_tracking=True)
    supplier_status_id = fields.Many2one(
        'custom.supplier.types.statuses', string='Supplier status', sub_tracking=True, ondelete='restrict')
    date_init = fields.Datetime(string='Date init', sub_tracking=True)
    date_end = fields.Datetime(string='Date end', sub_tracking=True)
    vacation_schedule_ids = fields.Many2many(
        comodel_name='custom.supplier.cost.product.schedule', string='Vacation schedules',
        domain=[('disabled', '=', False)], relation='vacation_schedule_cost_product_rel_id', ondelete='restrict')
    missing_value = fields.Boolean(string='Missing value', default=False)
    missing_values = fields.Text(string='Missing values')
    not_confirm = fields.Boolean(string='Not confirm', default=False, help="This field is used to avoid duplicated records")

    # === COMPUTE === #
    @api.depends('subservice_id')
    def _compute_mapping_product_ids(self):
        for rec in self:
            rec.mapping_product_ids = False
            if rec.subservice_id:
                matching_records = self.env['custom.product.mapping'].search([
                    ('product_id', '=', rec.subservice_id.id)
                ])
                parent_ids = matching_records.mapped('parent_id').ids
                rec.mapping_product_ids = [(6, 0, parent_ids)]

    @api.onchange(*REQUIRED_LINE_FIELDS)
    def _onchange_required_fields(self):
        """ Validar en batch si los campos requeridos están completos """
        required_fields = REQUIRED_LINE_FIELDS
        all_data = self.read(required_fields)
        for line, line_data in zip(self, all_data):
            missing = any(not line_data[f] for f in required_fields)
            line.missing_value = missing

    def action_open_missing_values(self):
        self.ensure_one()
        view_id = self.env.ref('custom_supplier_cost_matrix.custom_supplier_cost_product_view_form_popup').id
        return {
            'name': _("Missing Values"),
            'type': 'ir.actions.act_window',
            'res_model': 'custom.supplier.cost.product',
            'view_id': view_id,
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.id,
        }


class CustomSupplierCostMatrixLine(models.Model):
    _name = 'custom.supplier.cost.matrix.line'
    _description = 'Supplier Cost Matrix Line'
    _inherit = ['mail.thread']
    _rec_name = 'subservice_id'

    active = fields.Boolean(default=True, index=True)
    disabled = fields.Boolean(default=False, tracking=True)
    custom_supplier_cost_product_id = fields.Many2one(
        "custom.supplier.cost.product", string='Suplier cost matrix product')
    supplier_upload_cost_matrix_id = fields.Many2one(
        "custom.supplier.upload.cost.matrix", string='Supplier Cost Matrix', ondelete='restrict')
    supplier_center_id = fields.Many2one(
        comodel_name='res.partner', string='Center of attention', required=True,
        domain=[('parent_id.x_is_supplier', '=', True), ('type', '=', 'center'), ('disabled', '=', False)],
        ondelete='restrict', tracking=True, index=True)
    subservice_id = fields.Many2one('product.product', string='Subservice', required=True, tracking=True, index=True)
    country_id = fields.Many2one("res.country", string="Country", default=lambda self: self.env.company.country_id)
    state_id = fields.Many2one('res.country.state', string='Country State', tracking=True, index=True)
    geographical_area_id = fields.Many2one('custom.state.municipality', string='Geographical area', tracking=True, index=True)
    type_event_id = fields.Many2one('custom.type.event', string='Event type', required=True, tracking=True, index=True)
    concept_id = fields.Many2one(
        comodel_name='product.product', string='Concept', required=True, tracking=True,
        domain=[
            ('sale_ok', '=', False), ('purchase_ok', '=', True),
            ('x_concept_ok', '=', True), ('type', '=', 'service')
        ], index=True)
    subservice_specification_id = fields.Many2one(
        'custom.subservice.specification', string='Subservice Specification', tracking=True, index=True)
    # ToDo: Remove vehicle_category_id
    vehicle_category_id = fields.Many2one('fleet.vehicle.model.category', string='Category', tracking=True, index=True)
    account_id = fields.Many2one(
        comodel_name='res.partner',
        string='Account',
        domain=[('x_is_account', '=', True)],
        tracking=True, index=True)
    cost = fields.Float(string='Cost', required=True, tracking=True)
    holiday_date_applies = fields.Boolean(string="Holiday date applies", tracking=True)
    high_risk_area = fields.Boolean(related="geographical_area_id.red_zone", string="High risk area", tracking=True)
    active_agreement = fields.Boolean(string="Active agreement", tracking=True)
    supplier_status_id = fields.Many2one(
        'custom.supplier.types.statuses', string='Supplier status', required=True, tracking=True, index=True)
    date_init = fields.Datetime(string='Date init', tracking=True, index=True)
    date_end = fields.Datetime(string='Date end', tracking=True)
    vacation_schedule_ids = fields.Many2many(
        comodel_name='custom.supplier.cost.product.schedule', string='Vacation schedules',
        domain=[('disabled', '=', False)], relation='vacation_schedule_matrix_line_rel_id')
    state = fields.Selection(
        [("active", "Active"), ("inactive", "Inactive")],
        default='active', string="State", tracking=True)
