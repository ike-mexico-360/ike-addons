from odoo import models, fields


class IkeEventSupplierLink(models.Model):
    _inherit = 'ike.event.supplier.link'

    new_concept_ids = fields.Json(string='New Concept IDs', default=list)

    def write(self, vals):
        existing_lines_map = {link.id: link.supplier_product_ids.ids for link in self}

        res = super().write(vals)

        for link in self:
            all_ids = link.supplier_product_ids.ids
            new_ids = list(set(all_ids) - set(existing_lines_map[link.id]))

            new_lines = link.supplier_product_ids.filtered(
                lambda x: x.id in new_ids and not x.display_type
            )

            if new_lines:
                link.new_concept_ids = new_lines.ids

        return res
