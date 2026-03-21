import logging
import chardet
from io import StringIO
import csv
import base64
import json
import mimetypes
# from collections import defaultdict
from odoo import api, models, fields, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class CustomImportPostalCodes(models.TransientModel):
    _name = 'custom.import.postal_codes'
    _description = 'Custom Import Postal Codes'

    EXCEL_IMPORT_COLUMNS = [
        'd_codigo', 'd_asenta',
        'D_mnpio', 'd_estado', 'd_ciudad',
        'd_CP', 'c_estado',
        'c_mnpio', 'id_asenta_cpcons',
        'c_cve_ciudad'
    ]

    file = fields.Binary(string='File')
    file_name = fields.Char(string='File Name')
    file_type = fields.Char('File Type')

    @api.onchange('file')
    def _onchange_file(self):
        if self.file and self.file_name:
            mimetype, _ = mimetypes.guess_type(self.file_name)
            self.file_type = mimetype or 'application/octet-stream'

    def import_postal_codes(self):
        if not self.file:
            return False
        if self.file_type != 'text/plain':
            raise UserError(_("El archivo debe ser tipo TXT, tal cual como fué descargado."))

        required_columns = self.EXCEL_IMPORT_COLUMNS
        csv_file = self._convert_txt_to_csv_proper(self.file)
        json_data, file_size = self._convert_excel_data_to_json(
            csv_file, self.file_name, 'text/csv', required_columns
        )
        self._process_json_data(json_data, file_size)
        return True

    def _convert_txt_to_csv_proper(self, file):
        ''' Convertir TXT a CSV usando csv.writer con validación de encabezado '''
        try:
            # Decodificar el archivo
            file_bytes = base64.b64decode(file)

            # Detectar codificación
            encoding_info = chardet.detect(file_bytes)
            encoding = encoding_info.get('encoding', 'utf-8')
            file_content = file_bytes.decode(encoding)

            # Procesar líneas
            lines = file_content.splitlines()
            output = StringIO()
            csv_writer = csv.writer(output, delimiter='|')

            headers_written = False
            expected_first_header = "d_codigo"

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Saltar línea de descripción si existe
                if line.startswith('El Catálogo Nacional'):
                    continue

                if '|' in line:
                    parts = [part.strip() for part in line.split('|')]

                    # Validar si es el encabezado
                    if not headers_written:
                        if len(parts) > 0 and parts[0] == expected_first_header:
                            # Es el encabezado correcto
                            csv_writer.writerow(parts)
                            headers_written = True

                    else:
                        # Línea de datos normal
                        csv_writer.writerow(parts)

            # Obtener el contenido CSV
            csv_content = output.getvalue()
            output.close()

            # Validar que el CSV no esté vacío
            if not csv_content.strip():
                raise UserError(_("El archivo resultante está vacío después del procesamiento."))

            # Codificar a UTF-8
            csv_bytes = csv_content.encode('utf-8')
            csv_data = base64.b64encode(csv_bytes)

            return csv_data

        except Exception as e:
            raise UserError(_(f"Error al convertir TXT a CSV: {str(e)}"))

    def _convert_excel_data_to_json(self, file, file_name, file_type, required_columns):
        ''' Convertir excel al estilo JSON esperado '''
        # Validar que se cargó archivo
        if not file:
            raise UserError(_("No se ha cargado ningún archivo."))
        # Decodificar el archivo
        options = {
            'encoding': '',
            'separator': '|',
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
        # Leer los encabezados
        headers = rows[0]
        # Validar columnas requeridas
        missing_columns = [col for col in required_columns if col not in headers]
        if missing_columns:
            raise UserError(f"Faltan las siguientes columnas requeridas: {', '.join(missing_columns)}")
        # Obtener columnas requeridas
        column_indices = {col: idx for idx, col in enumerate(headers) if col in required_columns}
        if not column_indices:
            raise ValueError("Ninguna de las columnas requeridas está presente en el archivo.")
        records = [
            {col_name: row[col_id] for col_name, col_id in column_indices.items()}
            for row in rows[1:]  # Ignorar la fila de encabezados
        ]
        return records, file_size

    def _process_json_data(self, json_data, file_size):
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        # --- Limpiar datos anteriores en caso de haber
        self.env.cr.execute("""DELETE FROM custom_import_postal_codes_line;""")
        self.save_imported_data(json_data)  # Guardar la información obtenida del Excel en la base de datos
        self.update_states_like_sepomex()  # Actualizar los datos de los estados en Odoo según los declarados por SEPOMEX
        temporal_mnpios, to_delete_municipalities = self.process_municipalities()
        self.process_postal_codes(temporal_mnpios, file_size)
        self.delete_municipalities(to_delete_municipalities, self.get_models_to_check())
        # --- Limpiar datos actuales
        # self.env.cr.execute("""DELETE FROM custom_import_postal_codes_line;""")

    def save_imported_data(self, json_data):
        # --- Guardar los nuevos registros en la base de datos
        _logger.info(f"Guardando {len(json_data)} registros en la base de datos")
        values = []
        for rec in json_data:
            d_codigo = rec['d_codigo'].zfill(5)
            c_delta = f"{rec['c_estado'].zfill(2)}{rec['c_mnpio'].zfill(3)}"
            values.append(
                "('%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s')" %
                (
                    d_codigo, rec['d_asenta'], rec['D_mnpio'], rec['d_estado'], rec['d_ciudad'], rec['d_CP'],
                    rec['c_estado'], rec['c_mnpio'], rec['id_asenta_cpcons'], rec['c_cve_ciudad'], c_delta
                )
            )
        insert_query = """INSERT INTO custom_import_postal_codes_line (
            d_codigo, d_asenta, d_mnpio, d_estado, d_ciudad, d_cp, c_estado, c_mnpio, id_asenta_cpcons, c_cve_ciudad, c_delta
        ) VALUES %s;""" % (','.join(values))
        self.env.cr.execute(insert_query)
        _logger.info("Registros guardados en la base de datos")

    def update_states_like_sepomex(self):
        _logger.info("Actualizando estados en Odoo como estados declarados por SEPOMEX")
        # Hay estados que no coinciden en nombre, entonces utilizaremos equivalencia, la clave en minúsculas
        equivalent_state_names = {
            'Veracruz de Ignacio de la Llave': 'Veracruz',
            'Michoacán de Ocampo': 'Michoacán',
            'Coahuila de Zaragoza': 'Coahuila',
        }
        self.env.cr.execute("""SELECT DISTINCT d_estado, c_estado FROM custom_import_postal_codes_line;""")
        sepomex_states = self.env.cr.dictfetchall()

        self.env.cr.execute("""
            SELECT rcs.id, rcs.name AS d_estado, rcs.c_estado
            FROM res_country_state rcs
            INNER JOIN res_country rc ON rc.id = rcs.country_id
            WHERE rc.name->>'es_MX' ILIKE '%México%';
        """)
        odoo_states = self.env.cr.dictfetchall()
        odoo_states_dict = {state['d_estado']: state for state in odoo_states}

        count = 0
        for sepomex_state in sepomex_states:
            odoo_state = odoo_states_dict.get(sepomex_state['d_estado'], False)
            if not odoo_state:
                equivalent_name = equivalent_state_names.get(sepomex_state['d_estado'], False)
                if equivalent_name:
                    odoo_state = odoo_states_dict.get(equivalent_name, False)
            if not odoo_state:
                _logger.warning(f"No se encontró el estado declarado por SEPOMEX como: {sepomex_state['d_estado']}, en Odoo.")
                continue
            update_data = {}  # Para ejecutar solo si es necesario actualizar algo
            if odoo_state['d_estado'] != sepomex_state['d_estado']:
                update_data.update({'name': sepomex_state['d_estado']})
            if odoo_state['c_estado'] != sepomex_state['c_estado']:
                update_data.update({'c_estado': sepomex_state['c_estado']})
            if update_data:
                self.env['res.country.state'].browse([odoo_state['id']]).write(update_data)
                count += 1
        _logger.info(f"Se actualizó: {count} estados en Odoo.")

    def process_municipalities(self):
        _logger.info("Procesando municipios")
        # --- Obtener los registros de municipios distintos
        self.env.cr.execute("""
            SELECT DISTINCT d_mnpio, d_estado, c_estado, c_mnpio, c_delta
            FROM custom_import_postal_codes_line;
        """)
        distinct_data = self.env.cr.dictfetchall()
        imported_data_by_c_delta = {x['c_delta']: x for x in distinct_data}

        # --- Obtener los registros de municipios existentes en Odoo
        self.env.cr.execute("""
            SELECT csm.id, csm.name AS d_mnpio, rcs.name as d_estado, csm.c_estado, csm.c_mnpio, csm.c_delta
            FROM custom_state_municipality csm LEFT JOIN res_country_state rcs ON rcs.id = csm.state_id;
        """)
        odoo_data = self.env.cr.dictfetchall()
        odoo_data_by_c_delta = {x['c_delta']: x for x in odoo_data}

        # --- Comparar los valores existentes en Odoo vs los importados del Excel, obtener nuevos, obtener a eliminar y obtener
        # existentes a actualizar
        self.env.cr.execute("""SELECT id FROM res_country WHERE name->>'es_MX' ILIKE '%México%' LIMIT 1;""")
        country_id = self.env.cr.fetchone()[0]
        odoo_mx_states = self.env['res.country.state'].search_read([('country_id', '=', country_id)], ['name', 'country_id', 'code'])
        odoo_mx_states_dict = {rec['name'].lower(): rec['id'] for rec in odoo_mx_states}
        update_municipality_records = []  # Registros que existen en el Excel pero no en Odoo
        to_delete_municipalities = []  # Registros que faltan en el Excel
        new_municipality_records = []  # Registros que faltan en Odoo
        # Determinar los registros existentes en Odoo, pero no en el Excel para eliminarlos
        for c_delta, values in odoo_data_by_c_delta.items():
            if c_delta not in imported_data_by_c_delta:
                to_delete_municipalities.append(values)
        # Determinar los existentes en Odoo para actualizarlos y los no existentes para añadirlos
        for c_delta, values in imported_data_by_c_delta.items():
            estado = odoo_mx_states_dict.get(values['d_estado'].lower(), False)  # Buscar en minúsculas el estado
            # if not estado:
            #     if equivalent_state_names.get(values['d_estado'].lower(), False):
            #         estado = odoo_mx_states_dict.get(equivalent_state_names[values['d_estado'].lower()].lower(), False)
            if not estado:
                _logger.warning(f"No se encontró el estado {values['d_estado']} en Odoo")
                continue
            new_data = {
                'name': values['d_mnpio'],
                'country_id': country_id,
                'state_id': estado,
                'c_estado': values['c_estado'],
                'c_mnpio': values['c_mnpio'],
            }
            if c_delta in odoo_data_by_c_delta and c_delta not in to_delete_municipalities:
                odoo_record = odoo_data_by_c_delta[c_delta]
                if (odoo_record['d_mnpio'] != new_data['name'] or odoo_record['c_estado'] != new_data['c_estado']
                        or odoo_record['c_mnpio'] != new_data['c_mnpio']):
                    update_municipality_records.append({
                        'id': odoo_record['id'],
                        'values': new_data
                    })
            if c_delta not in odoo_data_by_c_delta and c_delta not in to_delete_municipalities:
                new_municipality_records.append(new_data)

        temporal_mnpios = {}
        if len(update_municipality_records) > 0:
            for rec in update_municipality_records:
                municipality_id = self.env['custom.state.municipality'].browse([rec['id']])
                municipality_id.write(rec['values'])
                temporal_mnpios.update({municipality_id.c_delta: municipality_id.id})
        if len(new_municipality_records) > 0:
            new_ids = self.env['custom.state.municipality'].create(new_municipality_records)
            temporal_mnpios.update({x.c_delta: x.id for x in new_ids})

        # CARGAR TODOS LOS MUNICIPIOS EXISTENTES (no solo nuevos/actualizados)
        self.env.cr.execute("""
            SELECT id, c_delta
            FROM custom_state_municipality;
        """)
        all_municipalities = self.env.cr.dictfetchall()
        for mun in all_municipalities:
            if mun['c_delta'] not in temporal_mnpios:  # No sobrescribir los ya procesados
                temporal_mnpios[mun['c_delta']] = mun['id']

        return temporal_mnpios, to_delete_municipalities  # Devolver el diccionario temporal y los que se borrarán

    def process_postal_codes(self, temporal_mnpios, file_size):
        def _get_file_size(file_size):
            # Convertir a formato legible (KB, MB, GB)
            str_file_size = "0 bytes"
            if file_size < 1024:
                str_file_size = f"{file_size} bytes"
            elif file_size < 1024 * 1024:
                str_file_size = f"{file_size / 1024:.2f} KB"
            elif file_size < 1024 * 1024 * 1024:
                str_file_size = f"{file_size / (1024 * 1024):.2f} MB"
            else:
                str_file_size = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
            return str_file_size

        _logger.info("Procesando códigos postales")
        # Procesar por lineas
        self.env.cr.execute("""
            SELECT id, zip_code AS d_codigo, city AS d_ciudad, municipality_id
            FROM custom_state_municipality_code
            WHERE active = True;
        """)
        active_odoo_postal_code = self.env.cr.dictfetchall()
        active_odoo_postal_code_dict = {f"{x['d_codigo']}&{x['d_ciudad']}": x for x in active_odoo_postal_code}

        self.env.cr.execute("""
            SELECT id, zip_code AS d_codigo, city AS d_ciudad, municipality_id
            FROM custom_state_municipality_code
            WHERE active = False;
        """)
        inactive_odoo_postal_code = self.env.cr.dictfetchall()
        inactive_odoo_postal_code_dict = {f"{x['d_codigo']}&{x['d_ciudad']}": x for x in inactive_odoo_postal_code}

        self.env.cr.execute("""SELECT DISTINCT d_codigo, d_ciudad, d_mnpio, c_delta FROM custom_import_postal_codes_line;""")
        excel_postal_codes = self.env.cr.dictfetchall()
        excel_postal_codes_dict = {f"{x['d_codigo']}&{x['d_ciudad']}": x for x in excel_postal_codes}

        update_codes_records = []  # Registros que existen en el Excel pero no en Odoo
        to_inactive_postal_codes = []  # Registros que faltan en el Excel
        to_reactive_postal_codes = []  # Registros que faltan existen en el Excel y en Odoo, pero están inactivos
        new_codes_records = []  # Registros que faltan en Odoo

        # Determinar los registros existentes en Odoo, pero no en el Excel para archivarlos
        for key, values in active_odoo_postal_code_dict.items():
            if key not in excel_postal_codes_dict:
                to_inactive_postal_codes.append(values)

        # Registros existentes en Odoo, pero que deben desarchivarse
        for key, values in inactive_odoo_postal_code_dict.items():
            if key in excel_postal_codes_dict:
                to_reactive_postal_codes.append(values)

        # Determinar los existentes en Odoo para actualizarlos y los no existentes para añadirlos
        for key, values in excel_postal_codes_dict.items():
            if key in active_odoo_postal_code_dict:
                odoo_record = active_odoo_postal_code_dict[key]
                if (odoo_record['d_ciudad'] != values['d_ciudad']):
                    update_codes_records.append({
                        'id': odoo_record['id'],
                        'values': {
                            'city': values['d_ciudad']
                        }
                    })
            elif key in inactive_odoo_postal_code_dict:
                odoo_record = inactive_odoo_postal_code_dict[key]
                if (odoo_record['d_ciudad'] != values['d_ciudad']):
                    update_codes_records.append({
                        'id': odoo_record['id'],
                        'values': {
                            'city': values['d_ciudad'],
                            'active': True
                        }
                    })
            else:
                c_delta = values['c_delta']
                municipality_id = temporal_mnpios.get(c_delta, False)
                if not municipality_id:
                    continue
                new_codes_records.append({
                    'zip_code': values['d_codigo'],
                    'city': values['d_ciudad'],
                    'municipality_id': municipality_id,
                    'c_delta': c_delta
                })

        if len(update_codes_records) > 0:
            for rec in update_codes_records:
                self.env['custom.state.municipality.code'].browse([rec['id']]).write(rec['values'])
            _logger.info(f"Se actualizaron {len(update_codes_records)} códigos postales")
        if len(new_codes_records) > 0:
            self.env['custom.state.municipality.code'].create(new_codes_records)
            _logger.info(f"Se añadieron {len(new_codes_records)} códigos postales")
        if len(to_inactive_postal_codes) > 0:
            # Solicitado, no se eliminan, se marcan como activo = False
            # self.env['custom.state.municipality.code'].browse([x['id'] for x in to_inactive_postal_codes]).unlink()
            # _logger.info(f"Se eliminaron {len(to_inactive_postal_codes)} códigos postales")
            self.env['custom.state.municipality.code'].browse([x['id'] for x in to_inactive_postal_codes]).write({'active': False})
            _logger.info(f"Se marcaron {len(to_inactive_postal_codes)} códigos postales como inactivos")
        if len(to_reactive_postal_codes) > 0:
            self.env['custom.state.municipality.code'].browse([x['id'] for x in to_reactive_postal_codes]).write({'active': True})
            _logger.info(f"Se reactivaron {len(to_reactive_postal_codes)} códigos postales")
        self.env['custom.import.postal_codes.log'].create({
            'file': self.file,
            'file_type': 'csv',
            'file_name': self.file_name,
            'file_size': _get_file_size(file_size),
            'import_date': fields.Datetime.now(),
            'imported_records': len(new_codes_records),
            'updated_records': len(update_codes_records),
            'deleted_records': len(to_inactive_postal_codes),
            'user_id': self.env.user.id,
        })

    def get_models_to_check(self):
        return {
            'custom_geographical_area': 'municipality_id',
        }

    def delete_municipalities(self, to_delete_municipalities, models_to_check=None):
        # Heredar o añadir los a models_to_check, sql_model: field para verificar relación antes de eliminar
        _logger.info("Eliminando municipios no existentes en SEPOMEX")
        if models_to_check is None:
            models_to_check = {}  # ejemplo: {'sale_order': 'municipality_id'}
        delete_records = []
        if len(to_delete_municipalities) > 0:
            for municipality in to_delete_municipalities:
                if models_to_check:
                    for model, field in models_to_check.items():
                        self.env.cr.execute("""SELECT id FROM %s WHERE %s IS NOT NULL LIMIT 1;""" % (model, field))
                        exist_record = self.env.cr.dictfetchone()
                        if exist_record:
                            _logger.warning(f"No se puede eliminar el municipio {municipality['d_mnpio']} con c_delta {municipality['c_delta']} porque existe una relación con {model}: {field} => {exist_record}")
                            continue
                        delete_records.append(municipality['id'])
                else:
                    delete_records.append(municipality['id'])
        if len(delete_records) > 0:
            self.env.cr.execute("""DELETE FROM custom_state_municipality WHERE id IN %s;""", [tuple(delete_records)])
        _logger.info(f"Se eliminaron {len(delete_records)} municipios")


class CustomImportPostalCodesLine(models.TransientModel):
    _name = 'custom.import.postal_codes.line'
    _description = 'Custom Import Postal Codes Line'

    d_codigo = fields.Char()
    d_asenta = fields.Char()
    d_mnpio = fields.Char()
    d_estado = fields.Char()
    d_ciudad = fields.Char()
    d_cp = fields.Char()
    c_estado = fields.Char()
    c_mnpio = fields.Char()
    id_asenta_cpcons = fields.Char()
    c_cve_ciudad = fields.Char()
    c_delta = fields.Char()


class CustomImportPostalCodesLog(models.Model):
    _name = "custom.import.postal_codes.log"
    _description = "Custom Import Postal Codes Log"

    file = fields.Binary(string="File")
    file_name = fields.Char(string="File Name")
    file_type = fields.Char("File Type")
    file_size = fields.Char(string="File Size")
    import_date = fields.Datetime(string="Import Date")
    imported_records = fields.Integer(string="Imported Records")
    updated_records = fields.Integer(string="Updated Records")
    deleted_records = fields.Integer(string="Deleted Records")
    user_id = fields.Many2one("res.users", string="User ID")
