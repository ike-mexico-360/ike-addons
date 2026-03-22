# -*- coding: utf-8 -*-

import re
import base64
import json
import logging
import mimetypes
import requests
from markupsafe import Markup

from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class CustomDataSource(models.Model):
    _name = 'custom.data.source'
    _description = 'Data Source'
    _order = 'create_date desc'
    _inherit = ['mail.thread']

    def _default_field_ids(self):
        return [
            Command.create({
                'field_name': 'membership_id',
                'source_field_name': '',
                'field_type': 'string',
                'field_required': True,
            }),
            Command.create({
                'field_name': 'clue',
                'source_field_name': '',
                'field_type': 'decimal',
                'field_required': True,
            }),
        ]

    # ToDo: Añadir validación de que al menos 1 campo sea clave
    # Campos debe ser A, B, etc

    name = fields.Char(required=True)

    client_id = fields.Many2one(
        'res.partner', string='Client', domain=[('x_is_client', '=', True), ('disabled', '=', False)], required=True, tracking=True)
    account_id = fields.Many2one(
        'res.partner', string='Account', domain=[('x_is_account', '=', True), ('disabled', '=', False)], required=True, tracking=True)

    # === FILENAME === #
    origin_type = fields.Selection([
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('txt', 'TXT'),
    ], string='Origin Type', default='excel', tracking=True, required=True)
    separator = fields.Selection([
        ('tab', ' TAB'),
        (',', ' ,'),
        (';', ' ;'),
        ('|', ' |'),
    ] , string='Separator', default=',', required=True)
    quote = fields.Selection([
        ('none', 'No quote'),
        ('\'', ' \''),
        ('"', ' "'),
    ], string='Quote', default='none', required=True)
    filename_pattern = fields.Char(string='Filename Pattern', tracking=True, required=True)
    filename_encoding = fields.Char(string='Filename Encoding', tracking=True, default='utf-8')
    filename_has_header = fields.Boolean(string='Filename Has Header', tracking=True)
    behavior = fields.Selection([
        ('append', 'Append'),
        ('full', 'Full'),
    ], string='Behavior', default='append', required=True)

    # destination_table = fields.Char(string='Destination Table', tracking=True)
    file_subdirectory = fields.Char(string='File Subdirectory', tracking=True)
    sftp_route = fields.Char(string='SFTP Route', tracking=True)
    template_file = fields.Binary('Template File')
    template_file_name = fields.Char('Template File Name')
    template_file_type = fields.Char('Template File Type')
    template_data_sampling = fields.Text()
    no_metadata = fields.Boolean(default=False)

    # === JOB === #
    job_enabled = fields.Boolean(string='Job Enabled', tracking=True)
    # job_schedule_cron = fields.Char(string='Job Schedule Cron', tracking=True)
    job_timezone = fields.Char(string='Job Timezone', tracking=True, default='America/Mexico_City', required=True)
    job_max_files_per_run = fields.Integer(string='Job Max Files Per Run', tracking=True, default=50)

    field_ids = fields.One2many(
        'custom.data.source.field', 'data_source_id',
        string='Fields',
        default=_default_field_ids)

    disabled = fields.Boolean(default=False, index=True, tracking=True)

    # === CONSTRAINS === #
    @api.constrains('account_id')
    def _check_account_id(self):
        for rec in self:
            domain = [('account_id', '=', rec.account_id.id), ('id', '!=', rec.id)]
            if self.search_count(domain + [('disabled', '=', False)]) > 0:
                raise ValidationError(_('A record with the same name already exists.'))
            elif self.search_count(domain + [('disabled', '=', True)]) > 0:
                raise ValidationError(_('A record with the same name already exists. It is disabled.'))

    # === ONCHANGE === #
    @api.onchange('account_id')
    def _onchange_account_id(self):
        self.ensure_one()
        self.client_id = False

    @api.onchange('template_file')
    def _onchange_template_file(self):
        if self.template_file and self.template_file_name:
            mimetype, _ = mimetypes.guess_type(self.template_file_name)
            self.template_file_type = mimetype or 'application/octet-stream'

    # === COMPUTE === #
    @api.depends('work_entry_type_by', 'work_entry_type_id', 'field_ids')
    def _compute_work_entry_types(self):
        for rec in self:
            if rec.work_entry_type_by == 'source':
                rec.work_entry_types = rec.work_entry_type_id.display_name
            elif rec.work_entry_type_by == 'row':
                rec.work_entry_types = _('Multiple')
            elif rec.work_entry_type_by == 'col':
                if len(rec.field_ids) > 5:
                    rec.work_entry_types = _('Multiple')
                else:
                    rec.work_entry_types = ', '.join(rec.field_ids.mapped('work_entry_type_id.display_name'))

    @api.depends('api_url', 'api_params')
    def _compute_api_url_result(self):
        for rec in self:
            url_result = ""
            if rec.origin_type == 'web_api' and rec.api_url:
                api_params = {}
                try:
                    rec.api_have_error = False
                    rec.api_settings_error = False
                    api_params = json.loads(rec.api_params)
                except json.JSONDecodeError:
                    rec.api_have_error = True
                    rec.api_settings_error = _("Invalid JSON data for API Params")
                    return
                result = rec._x_build_url(rec.api_url, api_params, raise_error=False)
                if result['error']:
                    rec.api_have_error = True
                    rec.api_settings_error = result['error']
                    url_result = result['url']
                else:
                    rec.api_have_error = False
                    rec.api_settings_error = False
                    url_result = result['url']
            rec.api_url_result = url_result

    @api.depends('origin_type', 'field_ids.field_name')
    def _compute_work_entry_type_code_alert(self):
        for rec in self:
            rec.work_entry_type_code_alert = rec.work_entry_type_by == 'row' and not any(
                field_id.field_name == 'work_entry_type_code'
                for field_id in rec.field_ids
            )

    # === ACTION === #
    def send_config_to_server(self):
        def _convert_odoo_type_to_api_type(odoo_type):
            api_type = {
                'str': 'string',
                'float': 'decimal',
            }.get(odoo_type, False)
            if not api_type:
                return odoo_type
            return api_type

        def _prepare_field_mapping(field):
            field_map = {
                "target": field.field_name or "",
                "source": field.source_field_name or "",
                "type": _convert_odoo_type_to_api_type(field.field_type),
                "required": field.field_required
            }
            if field.field_type == 'float':
                field_map.update({
                    "precision": field.precision,
                    "scale": field.scale,
                })
            return field_map

        self.ensure_one()
        # Validar sftp
        if not self.sftp_route or not self.file_subdirectory:
            raise UserError('SFTP route or file subdirectory is empty')

        # Validar que haya campos configurados
        if len(self.field_ids) == 0:
            raise UserError('No fields configured')

        # Validar que exista clave
        fields_clue = [x.field_name for x in self.field_ids.filtered(lambda x: x.field_clue) if x.field_name]
        if not fields_clue:
            raise UserError('No fields marked as Clue or field_name is empty')

        data = {
            "client_code": str(self.client_id.id),  # ToDo: Confirmar que es el valor correcto
            "description": "Integración para %s" % (self.client_id.name),
            "input_source": {
                "type": self.origin_type if self.origin_type == 'txt' else 'excel_csv',  # ToDo: Modificar, ya que reciben solo txt y excel_csv, así quedará?
                "filename_pattern": self.filename_pattern or "",
                "delimiter": self.separator,
                "quote_char": self.quote if self.quote != 'none' else None,
                "encoding": self.filename_encoding or "",
                "has_header": self.filename_has_header
            },
            "mapping": [
                _prepare_field_mapping(field) for field in self.field_ids
            ],
            "indexes": fields_clue,
            "behavior": self.behavior,
            "sftp": {
                "base_url": self.sftp_route or "",
                "subdirectory": self.file_subdirectory or ""
            },
            "job": {
                "enabled": self.job_enabled,
                # Diario o Semanal y horario de ejecución
                "schedule_cron": "0 */6 * * *",  # ! missing  ==> Confirmar que valores, horarios en Linux
                "timezone": self.job_timezone or "",
                "max_files_per_run": self.job_max_files_per_run
            }
        }

        # Leer url de parametros del sistema
        server_url = self.env['ir.config_parameter'].sudo().get_param('custom_master_catalog.source.external.url')
        if server_url:
            try:
                headers = {'Content-Type': 'application/json'}
                response = requests.post(url=server_url, headers=headers, data=json.dumps(data))
                _logger.info(response.json())
            except Exception as e:
                _logger.warning(f"Error en enviar la configuración a AWS: {str(e)}")

        _logger.warning(data)
        _logger.warning(server_url)

    def action_load_metadata(self):
        for rec in self:
            if rec.origin_type == 'excel':
                rec._load_excel_metadata()
            elif rec.origin_type == 'csv':
                rec._load_csv_metadata()
            elif rec.origin_type == 'web_api':
                rec._load_api_metadata()
            elif rec.origin_type == 'sql':
                rec._load_sql_metadata()

    # === PUBLIC === #
    def load_excel_data(self, file_data, file_name, file_type, options):
        base_import = self.env['base_import.import'].create({
            'file_name': file_name,
            'file_type': file_type,
        })
        if file_type == 'text/csv':
            base_import.file = base64.b64decode(file_data).decode('utf-8')
        else:  # Excel (xls, xlsx?)
            base_import.file = base64.b64decode(file_data)

        return base_import._read_file(options)

    def is_valid(self):
        self.ensure_one()
        fields = self.field_ids.mapped('field_name')
        if 'employee_code' not in fields or 'business_unit_code' not in fields:
            return False
        if self.work_entry_type_by == 'source':
            if 'work_entry_type_code' not in fields:
                return False

        return True

    # === PRIVATE === #
    def _load_excel_metadata(self):
        for rec in self:
            options = {
                'encoding': rec.filename_encoding,
                'separator': rec.separator,
                'quoting': rec.quote,
                'date_format': '',
                'datetime_format': '',
                'float_thousand_separator': ',',
                'float_decimal_separator': '.',
                'advanced': True,
                'has_headers': rec.filename_has_header,
                'keep_matches': False,
                'sheets': [],
                'sheet': ''
            }
            rows_count, rows = self.load_excel_data(
                rec.template_file,
                rec.template_file_name,
                rec.template_file_type,
                options)

            columns = rows[0]
            configured_columns = rec.field_ids.mapped('source_field_name')
            col_index = 0
            for col in columns:
                if col not in configured_columns:
                    field_data = {
                        'source_field_name': col,
                        'field_type': type(rows[1][col_index]).__name__,
                        'sequence': col_index + 10
                    }
                    # if rec.work_entry_type_by == 'col':
                    #     col_split = col.split(" ", 1)
                    #     if len(col_split) == 2 and col_split[0].isdigit():
                    #         work_entry_type_code = col_split[0]
                    #         work_entry_type_name = col_split[1]
                    #         work_entry_type = self.env['custom.pre.work.entry.type'].search_read([
                    #             ('code', '=', work_entry_type_code),
                    #             ('name', '=ilike', work_entry_type_name)
                    #         ], fields=['id'], limit=1)

                    #         if len(work_entry_type):
                    #             field_data['work_entry_type_id'] = work_entry_type[0]['id']

                    rec.field_ids = [Command.create(field_data)]
                col_index += 1

            rec.template_data_sampling = json.dumps(rows[:11])

    def _load_csv_metadata(self):
        for rec in self:
            options = {
                'encoding': rec.filename_encoding,
                'separator': rec.separator,
                'quoting': rec.quote,
                'date_format': '',
                'datetime_format': '',
                'float_thousand_separator': ',',
                'float_decimal_separator': '.',
                'advanced': True,
                'has_headers': rec.filename_has_header,
                'keep_matches': False,
                'sheets': [],
                'sheet': ''
            }
            _logger.warning(options)
            rows_count, rows = self.load_excel_data(
                rec.template_file,
                rec.template_file_name,
                rec.template_file_type,
                options)

            _logger.warning(rows)

            columns = rows[0]
            configured_columns = rec.field_ids.mapped('source_field_name')
            col_index = 0
            for col in columns:
                if col not in configured_columns:
                    field_data = {
                        'source_field_name': col,
                        'field_type': type(rows[1][col_index]).__name__,
                        'sequence': col_index + 10
                    }
                    # if rec.work_entry_type_by == 'col':
                    #     col_split = col.split(" ", 1)
                    #     if len(col_split) == 2 and col_split[0].isdigit():
                    #         work_entry_type_code = col_split[0]
                    #         work_entry_type_name = col_split[1]
                    #         work_entry_type = self.env['custom.pre.work.entry.type'].search_read([
                    #             ('code', '=', work_entry_type_code),
                    #             ('name', '=ilike', work_entry_type_name)
                    #         ], fields=['id'], limit=1)

                    #         if len(work_entry_type):
                    #             field_data['work_entry_type_id'] = work_entry_type[0]['id']

                    rec.field_ids = [Command.create(field_data)]
                col_index += 1

            rec.template_data_sampling = json.dumps(rows[:11])

    # def _load_api_metadata(self):
    #     no_data_rec_names = []
    #     for rec in self:
    #         url = rec.api_url_result
    #         method = rec.api_method
    #         api_data_json = json.loads(rec.api_data)
    #         body_data = json.dumps(api_data_json, sort_keys=True, default=str)
    #         response = False
    #         try:
    #             if method == 'get':
    #                 response = requests.get(url, headers={'Content-Type': 'application/json'}, timeout=10000)
    #             elif method == 'post':
    #                 response = requests.post(url, data=body_data, headers={'Content-Type': 'application/json'}, timeout=300)
    #             if response:
    #                 response.raise_for_status()
    #         except requests.exceptions.ReadTimeout as e:
    #             raise ValidationError(_(
    #                 "Web API call timed out after 300s - it may or may not have failed. "
    #                 "If this happens often, it may be a sign that the system you're "
    #                 "trying to reach is slow or non-functional.")) from e
    #         except requests.exceptions.RequestException as e:
    #             raise ValidationError(_("Web API call failed: %s", e)) from e
    #         except Exception as e:
    #             raise ValidationError(_("Wow, your web API call failed with a really unusual error: %s", e)) from e

    #         result = None
    #         if response and response.content:
    #             result = json.loads((response.content))
    #         # print("result", result)

    #         if result and len(result):
    #             configured_columns = rec.field_ids.mapped('source_field_name')
    #             columns = result[0].keys()

    #             for col in columns:
    #                 if col not in configured_columns:
    #                     rec.field_ids = [Command.create({
    #                         'source_field_name': col,
    #                         'field_type': 'str' or type(result[0][col]).__name__,
    #                     })]

    #                 rec.template_data_sampling = json.dumps(result[:11])
    #             rec.no_metadata = False
    #         else:
    #             no_data_rec_names.append(rec.name)
    #             rec.no_metadata = True

    #     if len(no_data_rec_names):
    #         message = _('There is no metadata for the data source')
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'type': 'warning',
    #                 'message': message + ': ' + ', '.join(no_data_rec_names),
    #                 'sticky': True,
    #                 'next': {'type': 'ir.actions.act_window_close'},
    #             }
    #         }

    # def _load_sql_metadata(self):
    #     for rec in self:
    #         sql_connection_string = rec.sql_connection_string
    #         sql_params = json.loads(rec.sql_params)
    #         sql_query_string = rec.sql_query_string.format(**sql_params)

    #         _logger.info(sql_connection_string)
    #         _logger.info(sql_query_string)

    #         # conn = pyodbc.connect(sql_connection_string)
    #         # cursor = conn.cursor()
    #         # cursor.execute(sql_query_string)

    #         # rows = cursor.fetchall()
    #         # print(rows)

    #         # columns = [column[0] for column in cursor.description]

    #         # results = []
    #         # for row in rows:
    #         #     results.append(dict(zip(columns, row)))

    #         # def datetime_handler(x):
    #         #     if isinstance(x, (datetime.date, datetime.datetime)):
    #         #         return x.isoformat()
    #         #     raise ValidationError("No serializable.")

    #         # rec.template_data_sampling = json.dumps(results, default=datetime_handler, ensure_ascii=False)

    #         # conn.close()

    # === DISABLE === #
    def action_disable(self, reason=None):
        for rec in self:
            if reason:
                body = Markup("""
                    <ul class="mb-0 ps-4">
                        <li>
                            <b>{}: </b><span class="">{}</span>
                        </li>
                    </ul>
                """).format(
                    _('Disabled'),
                    reason,
                )
                rec.message_post(
                    body=body,
                    message_type='notification',
                    body_is_html=True)
        return super().action_disable(reason)

    # @staticmethod
    # def _x_build_url(url_pattern, params, raise_error=True):
    #     """
    #     Construye una URL a partir de un patrón y un diccionario de parámetros.
    #     Args:
    #         url_pattern (str): La URL patrón con variables entre llaves.
    #         params (dict): Diccionario con las claves y valores para reemplazar las variables.
    #         raise_error (bool): Indica si se debe lanzar una excepción si falta una variable en el patrón.
    #     Returns:
    #         dict: La URL generada con los valores proporcionados y el mensaje de error.
    #     Raises:
    #         RaiseError: Si alguna variable en la URL patrón no está presente en el diccionario.
    #     """
    #     # Encuentra todas las variables {variable} en la URL patrón
    #     placeholders = re.findall(r'\{(.*?)\}', url_pattern)

    #     # Valida que todas las variables estén presentes en el diccionario
    #     missing_keys = [key for key in placeholders if key not in params]
    #     error_msg = False
    #     if missing_keys:
    #         error_msg = f"Faltan los siguientes parámetros en el diccionario: {', '.join(missing_keys)}"
    #         if raise_error:
    #             raise UserError(error_msg)

    #     # Reemplaza cada variable en la URL con su valor correspondiente
    #     present_keys = [key for key in placeholders if key in params]
    #     for key in present_keys:
    #         url_pattern = url_pattern.replace(f"{{{key}}}", str(params[key]))

    #     return {'url': url_pattern, 'error': error_msg}


class CustomDataSourceField(models.Model):
    _name = 'custom.data.source.field'
    _description = 'Data Source Field'
    _rec_name = 'field_name'
    _order = 'sequence'

    field_name = fields.Char('Field Destination')
    source_field_name = fields.Char('Field Source')
    data_source_id = fields.Many2one('custom.data.source')
    sequence = fields.Integer(default=5)
    field_type = fields.Selection([
        ('str', 'String'),
        ('int', 'Integer'),
        ('float', 'Decimal'),
        ('date', 'Date'),
        ('datetime', 'Datetime'),
        ('bool', 'Boolean'),
    ], string='Field Type', default='str', translate=False, required=True)
    precision = fields.Integer(string='Precision', default=10)
    scale = fields.Integer(string='Scale', default=0)
    field_longitude = fields.Integer(string='Longitude', default=10)
    field_required = fields.Boolean('Required')
    field_clue = fields.Boolean('Clue')
    field_un_search = fields.Char('UN Search')
    field_rule = fields.Char('Rule')

    # === ONCHANGE === #
    @api.onchange('work_entry_type_id')
    def _onchange_work_entry_type_id(self):
        if self.work_entry_type_id:
            self.field_name = ""
            if self.field_type not in ['int', 'float']:
                self.field_type = 'float'
            if self.data_source_id.origin_type == 'excel' and self.data_source_id.work_entry_type_by == 'col':
                self.source_field_name = self.work_entry_type_id.code + " " + self.work_entry_type_id.name

    # === CONSTRAINS === #
    @api.constrains('field_clue', 'data_source_id')
    def _check_unique_field_clue(self):
        for rec in self:
            if rec.field_clue and rec.data_source_id:
                clue_fields = self.search([
                    ('data_source_id', '=', rec.data_source_id.id),
                    ('field_clue', '=', True),
                    ('id', '!=', rec.id)
                ])
                if clue_fields:
                    raise ValidationError(
                        _('Only one field can be marked as Clue per Data Source. '
                        'The field "%s" is already marked as Clue.') % clue_fields[0].field_name
                    )
