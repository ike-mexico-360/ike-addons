from odoo import models, fields, _


class IkeEventSupplier(models.Model):
    _inherit = 'ike.event.supplier'

    def write(self, vals):
        vehicle_changes = {}

        evaluation_fields = {
            'evaluation_id',
            'evaluation_2_id',
            'evaluation_observations',
            'evaluation_informer',
        }
        evaluation_changes = evaluation_fields.intersection(vals)

        # Guardar el vehículo anterior
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

        res = super().write(vals)

        for rec in self:
            # ==== Bitácora cambio de vehiculo ==== #
            vehicle_change = vehicle_changes.get(rec.id)

            if vehicle_change:
                rec.event_id.with_context(
                    old_vehicle_id=vehicle_change['old_vehicle_id'],
                    old_vehicle_name=vehicle_change['old_vehicle_name'],
                    new_vehicle_id=(
                        rec.truck_id.id
                        if rec.truck_id
                        else False
                    ),
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

            # ==== Bitácora de evaluación ==== #
            if evaluation_changes:
                rec.event_id.with_context(
                    event_supplier_id=rec.id,
                    supplier_name=rec.supplier_id.display_name,

                    show_evaluation='evaluation_id' in vals,
                    evaluation=(
                        rec.evaluation_id.display_name
                        if rec.evaluation_id
                        else _('Not specified')
                    ),

                    show_reevaluation='evaluation_2_id' in vals,
                    reevaluation=(
                        rec.evaluation_2_id.display_name
                        if rec.evaluation_2_id
                        else _('Not specified')
                    ),

                    show_evaluation_observations=(
                        'evaluation_observations' in vals
                    ),
                    evaluation_observations=(
                        rec.evaluation_observations
                        or _('Not specified')
                    ),

                    show_evaluation_informer=(
                        'evaluation_informer' in vals
                    ),
                    evaluation_informer=(
                        rec.evaluation_informer
                        or _('Not specified')
                    ),
                )._create_message_binnacle(['ike_event_binnacle.ike_binnacle_supplier_evaluation'])

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
