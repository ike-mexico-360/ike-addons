# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api


class HelpdeskTicketCrm(models.Model):
    _inherit = 'sh.helpdesk.ticket'

    sh_lead_ids = fields.Many2many("crm.lead", string="Leads/Opportunities")
    lead_count = fields.Integer(
        'Lead', compute='_compute_lead_count_helpdesk')
    opportunity_count = fields.Integer(
        'Opportunity', compute='_compute_opportunity_count_helpdesk')

    def action_create_lead(self):
        context = {'default_type': 'lead'}
        if self.partner_id:
            context.update({
                'default_partner_id': self.partner_id.id,
            })
        if self.user_id:
            context.update({
                'default_user_id': self.user_id.id,
            })
        if self:
            context.update({
                'default_sh_ticket_ids': [(6, 0, self.ids)],
            })
        return{
            'name': 'Lead',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'context': context,
            'target': 'new'
        }

    def action_create_opportunity(self):
        context = {'default_type': 'opportunity'}
        if self.partner_id:
            context.update({
                'default_partner_id': self.partner_id.id,
            })
        if self.user_id:
            context.update({
                'default_user_id': self.user_id.id,
            })
        if self:
            context.update({
                'default_sh_ticket_ids': [(6, 0, self.ids)],
            })
        return{
            'name': 'Opportunity',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'context': context,
            'target': 'new'
        }

    def _compute_lead_count_helpdesk(self):
        for record in self:
            record.lead_count = 0
            leads = self.env['crm.lead'].search(
                [('id', 'in', record.sh_lead_ids.ids), '|', ('type', '=', 'lead'), ('type', '=', False)], limit=None)
            if leads:
                record.lead_count = len(leads.ids)

    def _compute_opportunity_count_helpdesk(self):
        for record in self:
            record.opportunity_count = 0
            opporunities = self.env['crm.lead'].search(
                [('id', 'in', record.sh_lead_ids.ids), ('type', '=', 'opportunity')], limit=None)
            if opporunities:
                record.opportunity_count = len(opporunities.ids)

    def lead_counts(self):
        self.ensure_one()
        leads = self.env['crm.lead'].search(
            [('id', 'in', self.sh_lead_ids.ids), '|', ('type', '=', 'lead'), ('type', '=', False)])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "crm.crm_lead_all_leads")
        if len(leads) > 1:
            action['domain'] = [('id', 'in', leads.ids), '|',
                                ('type', '=', 'lead'), ('type', '=', False)]
        elif len(leads) == 1:
            form_view = [(self.env.ref('crm.crm_lead_view_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + \
                    [(state, view)
                     for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = leads.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def opportunity_counts(self):
        self.ensure_one()
        opportunities = self.env['crm.lead'].search(
            [('id', 'in', self.sh_lead_ids.ids), ('type', '=', 'opportunity')])
        action = self.env["ir.actions.actions"]._for_xml_id(
            "crm.crm_lead_action_pipeline")
        if len(opportunities) > 1:
            action['domain'] = [('id', 'in', opportunities.ids),
                                ('type', '=', 'opportunity')]
        elif len(opportunities) == 1:
            form_view = [(self.env.ref('crm.crm_lead_view_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + \
                    [(state, view)
                     for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = opportunities.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action
