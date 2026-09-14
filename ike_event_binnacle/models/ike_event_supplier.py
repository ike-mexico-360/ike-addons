from odoo import models, fields, _


class IkeEventSupplier(models.Model):
    _inherit = 'ike.event.supplier'

    def write(self, vals):
        vehicle_changes = {}

        # Antes del super(), rec.truck_id es el vehículo anterior
        if 'truck_id' in vals:
            new_vehicle_id = vals.get('truck_id') or False

            for rec in self:
                if (
                    rec.truck_id
                    and rec.truck_id.id != new_vehicle_id
                ):
                    vehicle_changes[rec.id] = {
                        'old_vehicle_id': rec.truck_id.id,
                        'old_vehicle_name': rec.truck_id.display_name,
                    }

        # Ejecuta el write() original de ike.event.supplier
        res = super().write(vals)

        # Después del super(), rec.truck_id es el vehículo nuevo
        for rec in self:
            change = vehicle_changes.get(rec.id)

            if not change:
                continue

            rec.event_id.with_context(
                old_vehicle_id=change['old_vehicle_id'],
                old_vehicle_name=change['old_vehicle_name'],
                new_vehicle_id=rec.truck_id.id if rec.truck_id else False,
                new_vehicle_name=(
                    rec.truck_id.display_name
                    if rec.truck_id
                    else _('Not specified')
                ),
                event_supplier_id=rec.id,
            )._create_message_binnacle([
                'ike_event_binnacle.'
                'ike_binnacle_change_and_confirm_vehicle'
            ])

        return res


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
