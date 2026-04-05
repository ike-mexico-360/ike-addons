# -*- coding: utf-8 -*-

import base64
import mimetypes

from odoo import models, fields, api, _


class IkeEventEvidence(models.Model):
    _name = 'ike.event.evidence'
    _description = 'Event Evidence'
    _rec_name = 'event_id'

    event_id = fields.Many2one('ike.event', required=True)
    event_supplier_id = fields.Many2one('ike.event.supplier', ondelete='set null')

    evidence_type = fields.Selection([
        ('pickup', 'Pickup'),
        ('destination', 'Destination'),
        ('completed', 'Completed'),
        ('nu_evidence', 'Nu Evidence'),
    ], default='pickup', required=True)

    nu_user_code = fields.Char()
    nu_user_sign = fields.Binary()
    comments = fields.Text()
    extra_pay = fields.Boolean()
    extra_pay_amount = fields.Float()

    detail_ids = fields.One2many('ike.event.evidence.detail', 'event_evidence_id')
    detail_images = fields.Json(compute='_compute_detail_images')

    @api.depends('detail_ids.file_image')
    def _compute_detail_images(self):
        for rec in self:
            rec.detail_images = [
                {
                    'id': detail.id,
                    'image': detail.with_context(bin_size=False).file_image.decode('utf-8'),
                    'name': detail.file_name
                }
                for detail in rec.detail_ids if detail.file_image
            ]


class IkeEventEvidenceDetail(models.Model):
    _name = 'ike.event.evidence.detail'
    _description = 'Event Evidence Detail'
    _rec_name = 'file_name'

    event_evidence_id = fields.Many2one('ike.event.evidence', ondelete='cascade', required=True)
    file_name = fields.Char()
    file_image = fields.Image(required=True)
    side = fields.Selection([
        ('right', 'Right'),
        ('left', 'Left'),
        ('front', 'Front'),
        ('back', 'Back'),
        ('inside', 'Inside')
    ], string='Side')
