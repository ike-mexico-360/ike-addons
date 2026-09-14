# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class CustomSubserviceSpecification(models.Model):
    _inherit = 'custom.subservice.specification'

    assignment_type_ids = fields.Many2many(
        'ike.event.supplier.assignment.type',
        'custom_subservice_specification_supplier_assignment_type_rel',
        'subservice_specification_id',
        'assignment_type_id',
        'Assignment type',
        domain="[('disabled', '=', False), ('active', '=', True)]",
        default=lambda self: [
            self.env.ref('ike_event.ike_supplier_assignment_electronic').id,
            self.env.ref('ike_event.ike_supplier_assignment_publication').id,
            self.env.ref('ike_event.ike_supplier_assignment_manual').id,
        ],
        tracking=True,
    )
