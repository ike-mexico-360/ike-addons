# -- coding: utf-8 --

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)


class ResCountry(models.Model):
    _inherit = 'res.country'

    @api.depends('name', 'code', 'phone_code')
    def _compute_display_name(self):
        show_phone_format = self.env.context.get('show_country_phone_format', False)
        for record in self:
            if show_phone_format and record.code and record.phone_code:
                # When field is selected, show: "MX +52"
                record.display_name = f"{record.code} +{record.phone_code}"
            elif show_phone_format and record.code:
                # Fallback to just code if no phone_code
                record.display_name = record.code
            else:
                # Default behavior: show full country name
                record.display_name = record.name

    def name_get(self):
        """
        Override name_get to update display_name
        """
        result = []
        for record in self:
            # Default behavior: show full country name
            display_name = record.name

            result.append((record.id, display_name))
        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        """
        Override name_search to search by country name even when displaying code format
        """
        if self.env.context.get('show_country_phone_format'):
            # Search by full name but return in code format
            if name:
                # Search by name, code, or phone_code
                domain = args or []
                domain += [
                    '|', '|', '|',
                    ('name', operator, name),
                    ('code', operator, name),
                    ('phone_code', operator, name.lstrip('+')),
                    ('phone_code', operator, name)
                ]
                records = self.search(domain, limit=limit)
                return records.name_get()

        return super().name_search(name, args, operator, limit)
