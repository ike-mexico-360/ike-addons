# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IkeServiceInput(models.AbstractModel):
    _name = 'ike.service.input'
    _description = 'Service Input'

    name = fields.Char(copy=False)
    event_id = fields.Many2one('ike.event', ondelete='cascade', required=True, index=True)
    stage_ref = fields.Char(related='event_id.stage_ref')
    step_number = fields.Integer(related='event_id.step_number')
    event_supplier_number = fields.Integer(related='event_id.supplier_number', readonly=True)
    sections = fields.Json(related='event_id.sections')
    service_id = fields.Many2one(related='event_id.service_id')
    sub_service_id = fields.Many2one(related='event_id.sub_service_id')
    active = fields.Boolean(default=True)

    service_product_ids = fields.One2many(
        related='event_id.service_product_ids',
        string='Service concepts',
        readonly=False,
        copy=False,
    )

    products_count = fields.Integer(compute='_compute_products_count')

    @api.depends('service_product_ids')
    def _compute_products_count(self):
        for rec in self:
            rec.products_count = len(
                rec.service_product_ids.filtered(lambda x: x.supplier_number == rec.event_supplier_number)
            )

    ia_suggestion_loading = fields.Boolean()

    def set_event_summary_event_data(self):
        pass

    @api.model
    def get_google_api_key(self):
        return self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')

    def write(self, vals):
        # To Fix related and readonly=False. for some kind weird reason is and ike.event field o2m field set not an unlink
        if 'service_product_ids' in vals:
            to_delete = [x[1] for x in vals['service_product_ids'] if x[0] == 2]  # 2 == UNLINK
            others = [x for x in vals['service_product_ids'] if x[0] != 2]
            vals['service_product_ids'] = others
            event_product_ids = self.env['ike.event.product'].browse(to_delete)
            event_product_ids.unlink()
        return super().write(vals)

    def _check_own_required_fields(self, required_fields: list[str]):
        self.ensure_one()
        if not required_fields:
            return

        fields = self.fields_get(required_fields, attributes=['string', 'type'])

        empty_fields = []
        for field_name, field_info in fields.items():
            value = self[field_name]
            field_type = field_info.get('type')
            field_label = field_info.get('string')

            if field_type in ('many2one',):
                if not value:
                    empty_fields.append({
                        'name': field_name,
                        'label': field_label or field_name,
                    })
            elif field_type in ('one2many', 'many2many'):
                if not value:
                    empty_fields.append({
                        'name': field_name,
                        'label': field_label or field_name,
                    })
            elif field_type == 'boolean':
                pass
            else:
                if value is False or value is None or value == '':
                    empty_fields.append({
                        'name': field_name,
                        'label': field_label or field_name,
                    })

        if empty_fields:
            field_labels = []
            for field_name in empty_fields:
                field_labels.append(f"• {field_name['label']} ({field_name['name']})")

            raise UserError(
                _("Next field(s) are required:\n%s")
                % "\n".join(field_labels)
            )


class IkeServiceInputModel(models.AbstractModel):
    _name = 'ike.service.input.model'
    _inherit = ['ike.service.input']
    _description = 'Service Input Model'

    service_date = fields.Datetime(default=fields.Datetime.now, copy=False)

    # Location
    location_label = fields.Char(related='event_id.location_label', readonly=False)
    location_latitude = fields.Char(related='event_id.location_latitude', readonly=False)
    location_longitude = fields.Char(related='event_id.location_longitude', readonly=False)
    location_zip_code = fields.Char(related='event_id.location_zip_code', store=False, readonly=False)
    requires_federal_plates = fields.Boolean(related='event_id.requires_federal_plates', readonly=False)
    event_type_id = fields.Many2one(related='event_id.event_type_id', readonly=False)

    # Location Data
    street = fields.Char()
    street2 = fields.Char(string='Between streets')
    city = fields.Char()
    colony = fields.Char()
    # municipality = fields.Char()
    municipality_id = fields.Many2one(
        'custom.state.municipality', string='Municipality', ondelete='restrict',
        domain="[('state_id', '=', state_id)]")
    state_id = fields.Many2one(
        'res.country.state', string='State', ondelete='restrict',
        domain="[('country_id', '=', country_id)]")
    country_id = fields.Many2one('res.country', string='Country', ondelete='restrict')
    street_ref = fields.Char(string='References')
    street_number = fields.Char()

    @api.onchange('event_type_id')
    def _onchange_event_type_id(self):
        if self.event_type_id:
            self.requires_federal_plates = self.event_type_id.requires_federal_plates

    def set_event_summary_user_service_data(self):
        pass

    def set_event_summary_location_data(self):
        pass

    def set_event_summary_survey_data(self):
        pass

    def set_event_summary_destination_data(self):
        pass

    def set_event_summary_user_sub_service_data(self):
        pass

    def set_event_summary_supplier_data(self):
        pass
