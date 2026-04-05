# -*- coding: utf-8 -*-

import base64
import os

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IkeServiceVial(models.Model):
    _name = 'ike.service.input.vial'
    _inherit = ['ike.service.input.model', 'mail.thread', 'mail.tracking.duration.mixin']
    _description = 'Service Input Vial'
    _track_duration_field = 'stage_id'

    identification_type = fields.Selection([
        ('link', 'Link'),
        ('manual', 'Manual'),
    ], default='link')
    vehicle_plate_image = fields.Binary()
    vehicle_brand = fields.Char(string='Brand')
    vehicle_model = fields.Char(string='Subbrand')
    vehicle_year = fields.Char(string='Year')
    vehicle_plate = fields.Char(string='Plate')
    vehicle_color = fields.Char(string='Color')
    vehicle_nus_id = fields.Many2one('custom.nus.vehicle')
    vehicle_category_id = fields.Many2one(
        'fleet.vehicle.model.category',
        string='Category',
        domain="[('disabled', '=', False)]"
    )

    # === FLOW ACTIONS === #
    def _find_or_create_vehicle_brand(self):
        """Find existing vehicle brand or create new one if not found"""
        vehicle_brand_id = self.env['fleet.vehicle.model.brand'].search([
            ('name', '=ilike', self.vehicle_brand),
        ])
        if not vehicle_brand_id:
            vehicle_brand_id = self.env['fleet.vehicle.model.brand'].create({
                'name': self.vehicle_brand
            })
        return vehicle_brand_id

    def _find_or_create_vehicle_model(self):
        """Find existing vehicle model or create new one with brand association"""
        vehicle_model_id = self.env['fleet.vehicle.model'].search([
            ('name', '=ilike', self.vehicle_model),
        ])
        if not vehicle_model_id:
            vehicle_brand_id = self._find_or_create_vehicle_brand()
            vehicle_model_id = self.env['fleet.vehicle.model'].create({
                'name': self.vehicle_model,
                'brand_id': vehicle_brand_id.id
            })
        return vehicle_model_id

    def _find_or_create_nus_vehicle(self):
        """Find existing NUS vehicle by license plate or create new vehicle record"""
        if self.event_id.user_id and self.vehicle_plate:
            # Search for existing vehicle by encrypted license plate
            for vehicle in self.event_id.user_id.vehicle_nus_ids:
                if vehicle.check_encrypted_field('license_plate_nus', self.vehicle_plate):
                    return vehicle

            # Create new vehicle if not found
            vehicle_model_id = self._find_or_create_vehicle_model()
            vehicle_id = self.env['custom.nus.vehicle'].create({
                'nus_id': self.event_id.user_id.id,
                'model_nus_id': vehicle_model_id.id,
                'vehicle_year': self.vehicle_year,
                'vehicle_category_id': self.vehicle_category_id.id if self.vehicle_category_id else False,
                'license_plate_nus': self.vehicle_plate,
            })
            return vehicle_id
        return False

    def _update_vehicle_nus_reference(self):
        """Update the NUS vehicle reference based on current form data"""
        capturing_vehicle_data = self.stage_ref == "capturing" and self.step_number == 2
        if capturing_vehicle_data:
            vehicle_nus_id = self._find_or_create_nus_vehicle()
            self.vehicle_nus_id = vehicle_nus_id and vehicle_nus_id.id or False

    def set_event_summary_user_service_data(self):
        self._update_vehicle_nus_reference()
        for rec in self:
            rec.event_id.event_summary_id.user_service_data = {
                'title': f"<h4 class='text-ike-primary'>{_('Vehicle')}</h4>",
                'fields': [
                    {
                        'name': 'vehicle_brand',
                        'string': rec.fields_get(['vehicle_brand'])['vehicle_brand']['string'],
                        'type': rec.fields_get(['vehicle_brand'])['vehicle_brand']['type'],
                        'value': rec.vehicle_brand,
                    },
                    {
                        'name': 'vehicle_model',
                        'string': rec.fields_get(['vehicle_model'])['vehicle_model']['string'],
                        'type': rec.fields_get(['vehicle_model'])['vehicle_model']['type'],
                        'value': rec.vehicle_model,
                    },
                    {
                        'name': 'vehicle_year',
                        'string': rec.fields_get(['vehicle_year'])['vehicle_year']['string'],
                        'type': rec.fields_get(['vehicle_year'])['vehicle_year']['type'],
                        'value': rec.vehicle_year,
                    },
                    {
                        'name': 'vehicle_category_id',
                        'string': rec.fields_get(['vehicle_category_id'])['vehicle_category_id']['string'],
                        'type': 'char',
                        'value': rec.vehicle_category_id.name if rec.vehicle_category_id else False,
                    },
                    {
                        'name': 'vehicle_plate',
                        'string': rec.fields_get(['vehicle_plate'])['vehicle_plate']['string'],
                        'type': rec.fields_get(['vehicle_plate'])['vehicle_plate']['type'],
                        'value': rec.vehicle_plate,
                    },
                    {
                        'name': 'vehicle_color',
                        'string': rec.fields_get(['vehicle_color'])['vehicle_color']['string'],
                        'type': rec.fields_get(['vehicle_color'])['vehicle_color']['type'],
                        'value': rec.vehicle_color,
                    },
                ]
            }

    def set_event_summary_user_location_data(self):
        pass

    def set_event_summary_survey_data(self):
        pass

    def set_event_summary_destination_data(self):
        pass

    def set_event_summary_user_subservice_data(self):
        pass

    def set_event_summary_supplier_data(self):
        pass

    # === ACTIONS === #
    def action_identification_link(self):
        for rec in self:
            rec.identification_type = 'link'

    def action_identification_manual(self):
        for rec in self:
            rec.identification_type = 'manual'

    def action_identification_whatsapp(self):
        # ToDO: It is a dummy action
        self.ensure_one()
        module_path = os.path.dirname(os.path.abspath(__file__))
        image_path = os.path.join(
            module_path, "..", "..", "static", "description", "vehicle.png"
        )

        image_path = os.path.normpath(image_path)

        with open(image_path, "rb") as f:
            image_base64 = base64.b64encode(f.read())

        self.vehicle_plate_image = image_base64

        self.vehicle_brand = 'Mazda'
        self.vehicle_model = 'CX-3'
        self.vehicle_year = '2020'
        self.vehicle_plate = 'A00-AAA'
        self.vehicle_color = 'Gris'
        vehicle_category_id = self.env['fleet.vehicle.model.category'].search([
            ('name', '=ilike', 'Auto')], limit=1)
        self.vehicle_category_id = vehicle_category_id and vehicle_category_id.id or False
