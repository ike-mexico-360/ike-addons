# -*- coding: utf-8 -*-
import base64
import logging
import requests
from lxml import etree
from xml.etree import ElementTree as ET
from datetime import datetime, timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class CustomSatValidator(models.Model):
    _name = 'custom.sat.validator'
    _description = 'Autonomous SAT CFDI Validator (Multi-Package Container)'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default=lambda self: 'New')

    state = fields.Selection([
        ('draft', 'Draft / In Progress'),
        ('done', 'Fully Processed / Audited')
    ], string="Global Status", default='draft', tracking=True, readonly=True)

    purchase_id = fields.Many2one('purchase.order', string="Purchase Order", tracking=True)

    document_line_ids = fields.One2many(
        'custom.sat.validator.line',
        'validator_id',
        string='Document Packages'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.sudo().env['ir.sequence'].next_by_code('custom.sat.validator') or 'VAL/'
        return super(CustomSatValidator, self).create(vals_list)

    def action_process_and_validate_invoice_xml(self):
        """
        Main Orchestrator Action.
        Iterates over each document package line and triggers its standalone validation loop.
        """
        self.ensure_one()
        if not self.document_line_ids:
            raise ValidationError(_("Please add at least one document package to process."))

        for line in self.document_line_ids:
            line.action_process_line_workflow()

        if any(l.line_state == 'validated' for l in self.document_line_ids):
            self.write({'state': 'done'})

    def action_force_validate_xml_from_sat(self):
        """ Force validation by injecting the bypass flag into context """
        self.ensure_one()
        return self.with_context(bypass_po_validation=True).action_process_and_validate_invoice_xml()

    def action_draft(self):
        """ Resets the container and execution logs for all underlying lines """
        self.ensure_one()
        self.write({'state': 'draft'})
        for line in self.document_line_ids:
            line.action_reset_to_draft()
