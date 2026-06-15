import base64
import logging
import mimetypes
from io import BytesIO

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class CustomVehicleImportWizard(models.TransientModel):
    _name = 'custom.vehicle.import.wizard'
    _description = 'Import Supplier Users / Vehicles'

    file = fields.Binary(string='File', required=True)
    file_name = fields.Char(string='File name')
    file_type = fields.Char(string='File type')

    error_file = fields.Binary(string=' Errors', readonly=True)
    error_file_name = fields.Char(string='File name errors', readonly=True)

    summary_html = fields.Html(string='Summary', readonly=True)

    FILE_TYPES = {
        'csv': 'text/csv',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    }

    COLUMN_MAP = {
        'supplier_name': {
            'excel': 'Proveedor',
            'required': True,
            'type': 'char',
        },
        'center_name': {
            'excel': 'Centro de atención',
            'required': True,
            'type': 'char',
        },
        'user_login': {
            'excel': 'Correo',
            'required': True,
            'type': 'char',
        },
        'operator_name': {
            'excel': 'Operador',
            'required': False,
            'type': 'char',
        },
        'vehicle_ref': {
            'excel': 'Referencia del vehículo',
            'required': True,
            'type': 'char',
        },
        'vehicle_type': {
            'excel': 'Tipo de vehículo',
            'required': True,
            'type': 'char',
        },
        'plate': {
            'excel': 'Matrícula',
            'required': True,
            'type': 'char',
        },
        'federal_plate': {
            'excel': 'Placas federales',
            'required': False,
            'type': 'bool',
        },
        'tire_conditioning': {
            'excel': 'Gestiona acondicionamiento de llantas',
            'required': False,
            'type': 'bool',
        },
        'maneuvers': {
            'excel': 'Maniobras',
            'required': False,
            'type': 'bool',
        },
        'accessories': {
            'excel': 'Accesorios',
            'required': False,
            'type': 'char',
        },
        'year': {
            'excel': 'Año',
            'required': False,
            'type': 'char',
        },
        'model': {
            'excel': 'Modelo',
            'required': False,
            'type': 'char',
        },
        'weight_category': {
            'excel': 'Categoría de peso',
            'required': False,
            'type': 'char',
        },
    }

    RELATION_POLICIES = {
        'user': {
            'allow_create': True,
            'required': True,
        },
        'supplier': {
            'allow_create': False,
            'required': True,
        },
        'center': {
            'allow_create': False,
            'required': True,
        },
        'vehicle': {
            'allow_create': True,
            'required': True,
        },
    }

    @api.onchange('file', 'file_name')
    def _onchange_file(self):
        if self.file_name:
            mimetype, __ = mimetypes.guess_type(self.file_name)
            self.file_type = mimetype or 'application/octet-stream'
        else:
            self.file_type = False

    def action_import(self):
        self.ensure_one()

        rows = self._read_import_file()
        if not rows:
            raise UserError(_("The file does not contain information."))

        header = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []

        self._validate_columns(header)

        prepared_rows = self._prepare_rows(header, data_rows)
        if not prepared_rows:
            raise UserError(_("There are no rows with data to process."))

        processed_count = 0
        skipped_count = 0
        error_rows = []

        for row in prepared_rows:
            try:
                resolution = self._resolve_row_relations(row)
                row_errors = self._validate_row(row, resolution)

                if row_errors:
                    skipped_count += 1
                    error_rows.append(self._build_error_row(row, row_errors))
                    continue

                self._process_valid_row(row, resolution)
                processed_count += 1

            except Exception as exc:
                _logger.exception("Unexpected error importing row %s", row.get('_line_no'))
                skipped_count += 1
                error_rows.append(self._build_error_row(
                    row,
                    [_("Unexpected error: %s") % str(exc)]
                ))

        self._set_summary(processed_count, skipped_count, len(prepared_rows))

        if error_rows:
            self._generate_error_xlsx(error_rows)

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def _read_import_file(self):
        self.ensure_one()
        self._validate_uploaded_file()

        imported_file = self.env['base_import.import'].create({
            'res_model': self._name,
            'file': base64.b64decode(self.file),
            'file_name': self.file_name,
            'file_type': self.file_type,
        })

        rows_count, rows = imported_file._read_file(options={
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
            'sheet': '',
        })
        _logger.info("File read: %s rows=%s", self.file_name, rows_count)
        return rows

    def _validate_uploaded_file(self):
        self.ensure_one()

        if not self.file:
            raise UserError(_("No file has been loaded."))

        mimetype, __ = mimetypes.guess_type(self.file_name or '')
        self.file_type = mimetype or self.file_type or 'application/octet-stream'

        if self.file_type not in self.FILE_TYPES.values():
            raise UserError(_("The file must be type: %s") % ', '.join(self.FILE_TYPES.keys()))

    def _validate_columns(self, header):
        normalized_header = [self._normalize_header(col) for col in header]
        required_columns = [
            cfg['excel']
            for cfg in self.COLUMN_MAP.values()
            if cfg.get('required')
        ]

        missing_columns = [
            col for col in required_columns
            if self._normalize_header(col) not in normalized_header
        ]
        if missing_columns:
            raise UserError(_("Missing the following required columns: %s") % ', '.join(missing_columns))

    def _prepare_rows(self, header, data_rows):
        header_map = {
            self._normalize_header(col): idx
            for idx, col in enumerate(header)
        }

        result = []
        for line_no, row in enumerate(data_rows, start=2):
            if not row or not any(row):
                continue

            values = {'_line_no': line_no}
            for key, cfg in self.COLUMN_MAP.items():
                excel_name = self._normalize_header(cfg['excel'])
                col_idx = header_map.get(excel_name)
                cell = row[col_idx] if col_idx is not None and col_idx < len(row) else False
                values[key] = self._cast_cell_value(key, cell)

            missing_required = []
            for key, cfg in self.COLUMN_MAP.items():
                if cfg.get('required') and not values.get(key):
                    missing_required.append(cfg['excel'])

            if missing_required:
                result.append({
                    '_line_no': line_no,
                    '_skip_prevalidation': True,
                    '_prevalidation_errors': [
                        _("Missing required values: %s") % ', '.join(missing_required)
                    ],
                    **values,
                })
            else:
                result.append(values)

        return result

    def _resolve_row_relations(self, row):
        return {
            'user': self._resolve_user(row),
            'supplier': self._resolve_supplier(row),
            'center': self._resolve_center(row),
            'vehicle': self._resolve_vehicle(row),
        }

    # === RESOLVE RELATIONS === #
    def _resolve_user(self, row):
        login = row.get('user_login')
        if not login:
            return {'record': False, 'errors': [_("Did not indicate email to search user.")]}

        user = self.env['res.users'].sudo().search([('login', '=', login)], limit=1)

        if user:
            return {'record': user, 'errors': []}

        if not self.RELATION_POLICIES['user']['allow_create']:
            return {'record': False, 'errors': [_("User not found with login '%s'.") % login]}

        try:
            user = self._create_user_from_row(row)
            return {'record': user, 'errors': []}
        except Exception as exc:
            _logger.exception("Error creating user from import. login=%s", login)
            return {
                'record': False,
                'errors': [_("Could not create user with login '%s': %s") % (login, str(exc))]
            }

    def _resolve_supplier(self, row):
        name = row.get('supplier_name')
        if not name:
            return {'record': False, 'errors': [_("No supplier name was indicated.")]}

        supplier = self.env['res.partner'].sudo().search([
            ('name', '=', name),
            ('disabled', '=', False),
            ('x_is_supplier', '=', True),
        ], limit=1)

        if supplier:
            return {'record': supplier, 'errors': []}

        if not self.RELATION_POLICIES['supplier']['allow_create']:
            return {'record': False, 'errors': [_("Supplier not found with name '%s'.") % name]}

        try:
            supplier = self._create_supplier_from_row(row)
            return {'record': supplier, 'errors': []}
        except Exception as exc:
            _logger.exception("Error creating supplier from import")
            return {'record': False, 'errors': [_("Could not create supplier '%s': %s") % (name, str(exc))]}

    def _resolve_center(self, row):
        name = (row.get('center_name') or '').strip()
        if not name:
            return {'record': False, 'errors': [_("No center name was indicated.")]}

        center = self.env['res.partner'].sudo().search([
            ('name', '=', name),
            ('disabled', '=', False),
            ('type', '=', 'center'),
            ('parent_id.x_is_supplier', '=', True),
        ], limit=1)

        if center:
            return {'record': center, 'errors': []}

        if not self.RELATION_POLICIES['center']['allow_create']:
            return {'record': False, 'errors': [_("Center not found with name '%s'.") % name]}

        try:
            center = self._create_center_from_row(row)
            return {'record': center, 'errors': []}
        except Exception as exc:
            _logger.exception("Error creating center from import. center=%s", name)
            return {
                'record': False,
                'errors': [_("Could not create center '%s': %s") % (name, str(exc))]
            }

    def _resolve_vehicle(self, row):
        vehicle_ref = row.get('vehicle_ref')
        if not vehicle_ref:
            return {'record': False, 'errors': [_("No se indicó referencia del vehículo.")]}

        vehicle = self.env['fleet.vehicle'].sudo().search([
            ('x_vehicle_ref', '=', vehicle_ref),
        ], limit=1)

        if vehicle:
            return {'record': vehicle, 'errors': []}

        if not self.RELATION_POLICIES['vehicle']['allow_create']:
            return {
                'record': False,
                'errors': [_("No se encontró vehículo con referencia '%s'.") % vehicle_ref]
            }

        try:
            vehicle = self._create_vehicle_from_row(row)
            return {'record': vehicle, 'errors': []}
        except Exception as exc:
            _logger.exception("Error creando vehículo desde import. ref=%s", vehicle_ref)
            return {
                'record': False,
                'errors': [_("No se pudo crear vehículo con referencia '%s': %s") % (vehicle_ref, str(exc))]
            }

    # === CREATE METHODS === #
    def _create_user_from_row(self, row):
        Users = self.env['res.users'].sudo().with_context(no_reset_password=True)
        Partner = self.env['res.partner'].sudo()

        login = (row.get('user_login') or '').strip()
        operator_name = (row.get('operator_name') or '').strip() or login

        if not login:
            raise UserError(_("Could not create user without email/login."))

        existing_user = Users.search([('login', '=', login)], limit=1)
        if existing_user:
            return existing_user

        partner = Partner.search([
            ('email', '=', login),
            ('x_is_supplier', '=', False),
        ], limit=1)

        if not partner:
            partner = Partner.create({
                'name': operator_name,
                'email': login,
                'company_type': 'person',
                'x_is_supplier': False,
            })
        else:
            partner_vals = {}
            if operator_name and not partner.name:
                partner_vals['name'] = operator_name
            if login and not partner.email:
                partner_vals['email'] = login
            if partner_vals:
                partner.write(partner_vals)

        portal_group = self.env.ref('base.group_portal', raise_if_not_found=False)

        vals = {
            'name': operator_name,
            'login': login,
            'email': login,
            'partner_id': partner.id,
        }

        user = Users.create(vals)

        if portal_group:
            user.write({
                'groups_id': [(6, 0, [portal_group.id])],
            })

        return user

    def _create_supplier_from_row(self, row):
        vals = {
            'name': row.get('supplier_name'),
            'x_is_supplier': True,
            'disabled': False,
            'company_type': 'company',
            'supplier_rank': 1,
        }
        return self.env['res.partner'].sudo().create(vals)

    def _create_vehicle_from_row(self, row):
        Vehicle = self.env['fleet.vehicle'].sudo()
        VehicleModel = self.env['fleet.vehicle.model'].sudo()
        VehicleModelBrand = self.env['fleet.vehicle.model.brand'].sudo()

        vehicle_ref = (row.get('vehicle_ref') or '').strip()
        plate = (row.get('plate') or '').strip()
        model = (row.get('model') or '').strip()
        weigth_category = (row.get('weight_category') or '').strip()
        federal_plates = row.get('federal_plate', False)
        tire_conditioning = row.get('tire_conditioning', False)
        maneuvers = row.get('maneuvers', False)
        accessories = (row.get('accessories') or '').strip()
        year = (row.get('year') or '').strip()
        model_name = ""
        brand_name = ""
        if model:
            brand_name, model_name = model.split('/')

        if not vehicle_ref:
            raise UserError(_("Could not create vehicle without reference."))

        existing = Vehicle.search([('x_vehicle_ref', '=', vehicle_ref)], limit=1)
        if existing:
            return existing

        if not model_name:
            raise UserError(_("Could not create vehicle '%s' without the model data.") % vehicle_ref)

        model = VehicleModel.search([('name', '=', model_name.strip())], limit=1)

        if not model:
            brand = VehicleModelBrand.search([('name', '=', brand_name)], limit=1)
            if not brand:
                brand = VehicleModelBrand.create({
                    'name': brand_name,
                })
            weigth_vehicle_category = self.env['custom.vehicle.weight.category']
            if weigth_category:
                weigth_vehicle_category = self.env['custom.vehicle.weight.category'].search([
                    ('name', '=', weigth_category),
                ], limit=1)
            model = VehicleModel.create({
                'name': model_name,
                'brand_id': brand.id,
                'x_vehicle_weight_category_id': weigth_vehicle_category.id,
            })
        # Establecer la categoría de peso si no existe
        if model and not model.x_vehicle_weight_category_id and weigth_category:
            weigth_vehicle_category = self.env['custom.vehicle.weight.category'].search([
                ('name', '=', weigth_category),
            ], limit=1)
            if weigth_vehicle_category:
                model.write({
                    'x_vehicle_weight_category_id': weigth_vehicle_category.id,
                })

        accessory_ids = self.env['product.product']
        if accessories:
            accessories = accessories.split(',')
            accessories = [a.strip() for a in accessories]
            accessories_domain = self.env['product.product'].get_accessories_domain()
            accessories_domain.append(('name', 'in', accessories))
            accessory_ids = self.env['product.product'].search(accessories_domain)

        vals = {
            'model_id': model.id,
            'license_plate': plate or False,
            'x_vehicle_ref': vehicle_ref,
            'x_vehicle_service_state': 'available',
            'x_federal_license_plates': federal_plates,
            'x_manages_tire_conditioning': tire_conditioning,
            'x_maneuvers': maneuvers,
            'x_accessories': accessory_ids.ids,
            'model_year': year or False,
        }

        return Vehicle.create(vals)

    def _create_center_from_row(self, row):
        Partner = self.env['res.partner'].sudo()

        center_name = (row.get('center_name') or '').strip()
        supplier_name = (row.get('supplier_name') or '').strip()

        if not center_name:
            raise UserError(_("Could not create center without name."))

        if not supplier_name:
            raise UserError(_("Could not create center '%s' without supplier.") % center_name)

        supplier = Partner.search([
            ('name', '=', supplier_name),
            ('disabled', '=', False),
            ('x_is_supplier', '=', True),
        ], limit=1)

        if not supplier:
            if self.RELATION_POLICIES['supplier']['allow_create']:
                supplier = self._create_supplier_from_row(row)
            else:
                raise UserError(_("Supplier '%s' does not exist to create center '%s'.") % (supplier_name, center_name))

        existing_center = Partner.search([
            ('name', '=', center_name),
            ('parent_id', '=', supplier.id),
            ('type', '=', 'center'),
        ], limit=1)
        if existing_center:
            return existing_center

        vals = {
            'name': center_name,
            'parent_id': supplier.id,
            'type': 'center',
            'company_type': 'person',  # ? debe ser company?
            'disabled': False,
            'x_is_supplier': False,
        }

        return Partner.create(vals)

    # === AUXILIAR METHODS === #
    def _validate_row(self, row, resolution):
        errors = []

        if row.get('_skip_prevalidation'):
            errors.extend(row.get('_prevalidation_errors', []))
            return errors

        for relation_key in ('user', 'supplier', 'center', 'vehicle'):
            errors.extend(resolution[relation_key]['errors'])

        user = resolution['user']['record']
        supplier = resolution['supplier']['record']
        center = resolution['center']['record']
        vehicle = resolution['vehicle']['record']

        if supplier and center and center.parent_id != supplier:
            errors.append(
                _("Center '%s' does not belong to supplier '%s'.")
                % (center.display_name, supplier.display_name)
            )

        if user:
            existing_rel = self.env['res.partner.supplier_users.rel'].sudo().search([
                ('user_id', '=', user.id),
            ], limit=1)
            if existing_rel:
                errors.append(
                    _("User '%s' already assigned in supplier-user relation.")
                    % (user.display_name,)
                )

        if user and vehicle:
            user_partner = user.partner_id

            if vehicle.driver_id and vehicle.driver_id != user_partner:
                errors.append(
                    _("Vehicle '%s' already has assigned another driver: '%s'.")
                    % (vehicle.display_name, vehicle.driver_id.display_name)
                )

            other_vehicle = self.env['fleet.vehicle'].sudo().search([
                ('driver_id', '=', user_partner.id),
                ('id', '!=', vehicle.id),
            ], limit=1)
            if other_vehicle:
                errors.append(
                    _("User '%s' already assigned as driver in vehicle '%s'.")
                    % (user.display_name, other_vehicle.display_name)
                )

        return errors

    def _process_valid_row(self, row, resolution):
        user = resolution['user']['record']
        center = resolution['center']['record']
        vehicle = resolution['vehicle']['record']

        rel_vals = {
            'user_id': user.id,
            'user_type': 'operator',
            'center_of_attention_id': center.id,
        }
        relation = self.env['res.partner.supplier_users.rel'].sudo().create(rel_vals)

        user_partner = user.partner_id
        if vehicle and user_partner:
            vehicle_data = {
                'x_partner_id': center.parent_id.id,
                'x_center_id': center.id,
            }
            if not vehicle.driver_id:
                vehicle_data['driver_id'] = user_partner.id
            elif vehicle.driver_id == user_partner:
                pass
            else:
                # Tentativo para futuro: reemplazar si se habilita política de actualización
                pass
            vehicle.sudo().write(vehicle_data)

        return relation

    def _generate_error_xlsx(self, error_rows):
        if not xlsxwriter:
            raise UserError(_("The xlsxwriter library is not available to generate the import errors file."))

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Import errors')

        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9EAF7',
            'border': 1,
        })
        cell_format = workbook.add_format({'border': 1, 'valign': 'top'})
        wrap_format = workbook.add_format({'border': 1, 'text_wrap': True, 'valign': 'top'})

        headers = [
            'Línea',
            'Proveedor',
            'Centro de atención',
            'Correo',
            'Operador',
            'Referencia del vehículo',
            'Estado',
            'Motivo(s)',
        ]

        for col, title in enumerate(headers):
            sheet.write(0, col, title, header_format)

        for row_idx, err in enumerate(error_rows, start=1):
            sheet.write(row_idx, 0, err.get('line_no'), cell_format)
            sheet.write(row_idx, 1, err.get('supplier_name'), cell_format)
            sheet.write(row_idx, 2, err.get('center_name'), cell_format)
            sheet.write(row_idx, 3, err.get('user_login'), cell_format)
            sheet.write(row_idx, 4, err.get('operator_name'), cell_format)
            sheet.write(row_idx, 5, err.get('vehicle_ref'), cell_format)
            sheet.write(row_idx, 6, err.get('status'), cell_format)
            sheet.write(row_idx, 7, '\n'.join(err.get('errors', [])), wrap_format)

        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 2, 30)
        sheet.set_column(3, 4, 28)
        sheet.set_column(5, 5, 24)
        sheet.set_column(6, 6, 15)
        sheet.set_column(7, 7, 60)

        workbook.close()
        output.seek(0)

        self.write({
            'error_file': base64.b64encode(output.getvalue()),
            'error_file_name': 'errores_importacion_usuarios_proveedor.xlsx',
        })

    def _build_error_row(self, row, errors):
        return {
            'line_no': row.get('_line_no'),
            'supplier_name': row.get('supplier_name'),
            'center_name': row.get('center_name'),
            'user_login': row.get('user_login'),
            'operator_name': row.get('operator_name'),
            'vehicle_ref': row.get('vehicle_ref'),
            'status': 'Omitido',
            'errors': errors,
        }

    def _set_summary(self, processed_count, skipped_count, total_count):
        self.summary_html = """
            <div>
                <p><b>%s</b> %s</p>
                <p><b>%s</b> %s</p>
                <p><b>%s</b> %s</p>
            </div>
        """ % (_("Total rows evaluated:"), total_count, _("Rows processed:"), processed_count, _("Rows skipped:"), skipped_count)

    def _normalize_header(self, value):
        return (value or '').strip().lower()

    def _cast_cell_value(self, field_key, value):
        field_cfg = self.COLUMN_MAP.get(field_key, {})
        field_type = field_cfg.get('type', 'char')

        value = self._normalize_value(value)

        if value is False:
            return False

        if field_type == 'bool':
            return self._to_bool(value)

        if field_type == 'int':
            if value in (False, '', None):
                return False
            try:
                return int(float(value))
            except (ValueError, TypeError):
                raise UserError(_("The value '%s' in column '%s' is not a valid integer.") % (
                    value, field_cfg.get('excel', field_key)
                ))

        return value

    def _to_bool(self, value):
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return bool(value)

        if isinstance(value, str):
            normalized = value.strip().lower()
            true_values = {'1', 'true', 't', 'yes', 'y', 'si', 'sí', 'verdadero', 'x'}
            false_values = {'0', 'false', 'f', 'no', 'n', 'falso', ''}

            if normalized in true_values:
                return True
            if normalized in false_values:
                return False

        raise UserError(_("Could not convert value '%s' to boolean.") % value)

    def _normalize_value(self, value):
        if value is None:
            return False
        if isinstance(value, str):
            value = value.strip()
            return value or False
        return value
