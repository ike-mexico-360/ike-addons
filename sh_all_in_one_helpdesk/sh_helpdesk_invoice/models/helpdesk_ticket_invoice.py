# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields,_
from odoo.exceptions import ValidationError


class HelpdeskTicketInvoice(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    sh_invoice_ids = fields.Many2many("account.move", string="Invoices")
    invoice_count = fields.Integer('Invoice',
                                   compute='_compute_invoice_count_helpdesk')

    def action_create_invoice(self):
        vals = {
            'move_type': 'out_invoice',
        }
        if self.partner_id:
            vals.update({
                'partner_id': self.partner_id.id,
            })
        if self.user_id:
            vals.update({
                'user_id': self.user_id.id,
            })
        if self:
            vals.update({
                'sh_ticket_ids': [(6, 0, self.ids)],
            })
        if self.product_ids:
            invoice_id = self.env['account.move'].create(vals)
            line_list = []
            for product in self.product_ids:
                journal_id = self.env["account.journal"].search(
                    [("type", "=", "sale"),('company_id', '=', self.env.company.id)],
                    limit=None)
                account_id = False
                if journal_id.default_account_id:
                    account_id = journal_id.default_account_id
                if account_id:
                    line_vals = {
                        'product_id': product.id,
                        'display_type':'product',
                        'move_id':invoice_id.id,
                        'name': product.display_name,
                        'quantity': 1.0,
                        'price_unit': product.list_price,
                        'product_uom_id': product.uom_id.id,
                        'account_id': account_id.id,
                        'currency_id': self.company_id.currency_id.id,
                    }
                    if product.taxes_id:
                        line_vals.update(
                            {'tax_ids': [(6, 0, product.taxes_id.ids)]})
                    line_list.append((0, 0, line_vals))
            invoice_id.invoice_line_ids = line_list
            return {
                'name': 'Customer Invoice',
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id':invoice_id.id,
                'target': 'new'
            }
        else:
            raise ValidationError(_('Please select product for create Invoice'))
    def _compute_invoice_count_helpdesk(self):
        for record in self:
            record.invoice_count = 0
            tickets = self.env['account.move'].search(
                [('id', 'in', record.sh_invoice_ids.ids)], limit=None)
            record.invoice_count = len(tickets.ids)

    def invoice_counts(self):
        self.ensure_one()
        orders = self.env['account.move'].search([
            ('id', 'in', self.sh_invoice_ids.ids)
        ])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_out_invoice_type")
        if len(orders) > 1:
            action['domain'] = [('id', 'in', orders.ids)]
        elif len(orders) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + \
                    [(state, view)
                     for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = orders.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action