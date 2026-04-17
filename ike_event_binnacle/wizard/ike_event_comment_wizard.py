import logging
from odoo import models, fields, api
# from datetime import datetime

_logger = logging.getLogger(__name__)


class IkeEventCommentWizard(models.TransientModel):
    _name = 'ike.event.comment.wizard'
    _description = 'Event Comment Wizard'

    event_id = fields.Many2one(
        'ike.event',
        required=True
    )
    body = fields.Html(
        string='Comment',
        required=True
    )
    event_binnacle_id = fields.Many2one(
        'ike.event.binnacle',
        compute="_compute_event_binnacle"
    )
    is_supplier = fields.Boolean(string="Is supplier?")
    count_supplier = fields.Integer()
    x_supplier_message_id = fields.Many2one('res.partner', string='Supplier')
    x_supplier_message_binnacle_domain = fields.Binary(string="Supplier domain", compute="_compute_supplier_message_binnacle_domain")

    # === COMPUTE === #
    @api.depends('event_id')
    def _compute_event_binnacle(self):
        for rec in self:
            rec.event_binnacle_id = False
            message_id = rec._get_last_message_event()

            if not message_id or not message_id.event_binnacle_id:
                continue

            event_binnacle_id = self.env['ike.event.binnacle'].sudo().search([
                ('disabled', '=', False),
                ('event_stage_id', '=', message_id.event_binnacle_id.event_stage_id.id),
                ('step_number', '=', message_id.event_binnacle_id.step_number),
                ('binnacle_category_id.name', '=', 'Resumen'),
            ], limit=1)

            rec.event_binnacle_id = event_binnacle_id

    @api.depends('event_id')
    def _compute_supplier_message_binnacle_domain(self):
        for rec in self:
            if rec.event_id:
                supplier = []

                for supplier_cancel in rec.event_id.selected_supplier_ids:
                    if supplier_cancel.state not in ['cancel', 'cancel_supplier', 'cancel_event']:
                        supplier.append(supplier_cancel.mapped('supplier_id').id)
                        print("supplier", supplier)

                domain = [('id', 'in', supplier)]
                rec.x_supplier_message_binnacle_domain = domain

    @api.onchange('is_supplier', 'event_id')
    def _onchange_supplier(self):
        for rec in self:
            if not rec.is_supplier:
                rec.x_supplier_message_id = False
                rec.count_supplier = 0
                continue

            # Obtener proveedores válidos
            suppliers = rec.event_id.selected_supplier_ids.filtered(
                lambda s: s.state not in ['cancel', 'cancel_supplier', 'cancel_event']
            ).mapped('supplier_id')

            # Contador
            rec.count_supplier = len(suppliers)
            print("Contador:", rec.count_supplier)

            # Auto selección SOLO si hay uno
            if rec.count_supplier == 1:
                rec.x_supplier_message_id = suppliers[0]
            else:
                rec.x_supplier_message_id = False

    # === METHODS === #
    def _get_last_message_event(self):
        message_id = self.env['mail.message'].sudo().search([
            ('event_binnacle_id', '!=', False),
            ('model', '=', "ike.event"),
            ('res_id', '=', self.event_id.id),
        ], order='create_date desc', limit=1)

        return message_id

    # Auxiliar para recibir mensajes desde el módulo o externo
    def _save_message(self, event_id, author_id, body, event_binnacle_id):
        try:
            supplier_name = self.env.context.get('supplier')
            self.env['mail.message'].create({
                'model': 'ike.event',
                'res_id': event_id.id,
                'body': body,
                'message_type': 'comment',
                'subtype_id': self.env.ref('mail.mt_comment').id,
                'author_id': author_id.id,
                'supplier': supplier_name,
                'is_internal': False,
                'event_binnacle_id': event_binnacle_id.id,
            })
            return True
        except Exception as e:
            _logger.warning(f'Error sending comment: {str(e)}')
            return False

    # === ACTIONS === #
    def action_save_confirm(self):
        self.ensure_one()

        self.with_context(supplier=self.x_supplier_message_id.name)._save_message(
            event_id=self.event_id,
            author_id=self.env.user.partner_id,
            body=self.body,
            event_binnacle_id=self.event_binnacle_id
        )

        return {'type': 'ir.actions.act_window_close'}

    def action_save_external_message(self, author_id):
        """ Save message from external source, with determinated author and body """
        return self._save_message(
            event_id=self.event_id,
            author_id=author_id,
            body=self.body,
            event_binnacle_id=self.event_binnacle_id
        )
