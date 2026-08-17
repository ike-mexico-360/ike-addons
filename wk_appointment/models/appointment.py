# -*- coding: utf-8 -*-
#################################################################################
# Author      : Webkul Software Pvt. Ltd. (<https://webkul.com/>)
# Copyright(c): 2015-Present Webkul Software Pvt. Ltd.
# License URL : https://store.webkul.com/license.html/
# All Rights Reserved.
#
#
#
# This program is copyright property of the author mentioned above.
# You can`t redistribute it and/or modify it.
#
#
# You should have received a copy of the License along with this program.
# If not, see <https://store.webkul.com/license.html/>
#################################################################################

from odoo import models,fields,api,_
from odoo.exceptions import UserError,ValidationError
from datetime import date,datetime,timedelta
import dateutil
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, float_is_zero
import pytz, time, math
from dateutil.relativedelta import relativedelta
from pytz import timezone
import logging
_logger = logging.getLogger(__name__)
D = {
    0: 'monday',
    1: 'tuesday',
    2: 'wednesday',
    3: 'thursday',
    4: 'friday',
    5: 'saturday',
    6: 'sunday',
}


class Appointment(models.Model):
    _name = "appointment"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'id desc, appoint_date desc'
    _description = "Appointment"

    @api.model
    def get_appoint_pricelist_price(self, pricelist_id, prod_tmpl_id, appoint_charge):
        prod_pricelist_obj = self.env['product.pricelist'].sudo().browse(int(pricelist_id))
        appoint_charge = prod_pricelist_obj._get_product_price(quantity=1, product=prod_tmpl_id)
        return appoint_charge

    @api.depends('appoint_lines.price_total')
    def _amount_all(self):
        for rec in self:
            amount_untaxed = amount_tax = 0.0
            for line in rec.appoint_lines:
                amount_untaxed += line.price_subtotal
                amount_tax += line.price_tax
            rec.update({
                'amount_untaxed': amount_untaxed,
                'amount_tax': amount_tax,
                'amount_total': amount_untaxed + amount_tax,
            })

    @api.depends('appoint_person_id')
    def compute_appointment_address(self):
        for rec in self:
            if rec.appoint_person_id:
                if rec.appoint_person_id.use_addr_as_appoint:
                    rec.app_street1 = rec.appoint_person_id.street
                    rec.app_street2 = rec.appoint_person_id.street2
                    rec.app_city = rec.appoint_person_id.city
                    rec.app_state_id = rec.appoint_person_id.state_id
                    rec.app_zip = rec.appoint_person_id.zip
                    rec.app_country_id = rec.appoint_person_id.country_id
                    rec.app_phone = rec.appoint_person_id.phone
                    rec.app_email = rec.appoint_person_id.email
                else:
                    rec.app_street1 = self.env.user.company_id.street
                    rec.app_street2 = self.env.user.company_id.street2
                    rec.app_city = self.env.user.company_id.city
                    rec.app_state_id = self.env.user.company_id.state_id
                    rec.app_zip = self.env.user.company_id.zip
                    rec.app_country_id = self.env.user.company_id.country_id
                    rec.app_phone = self.env.user.company_id.phone
                    rec.app_email = self.env.user.company_id.email
        return

    @api.model
    def compute_default_group(self):
        return False

    @api.model
    def set_default_source(self):
        source = False
        try:
            source = self.env.sudo().ref('wk_appointment.appoint_source1')
            if source and source.company_id.id != self.env.user.company_id.id:
                return False
        except Exception as e:
            pass
        return source

    name = fields.Char(string="Number", default="New", copy=False)
    customer = fields.Many2one("res.partner", "Customer", required=True)
    appoint_date = fields.Date(string="Appointment Date", required=True, default=fields.Date.context_today, copy=False)
    appoint_group_id = fields.Many2one(
        comodel_name="appointment.person.group",
        string="Appointment With",
        tracking=True,
        default=compute_default_group,
        )
    appoint_person_id = fields.Many2one(
        comodel_name="res.partner",
        string="Appointee",
        tracking=True,
        domain="['|', ('company_id', '=', False),('company_id', '=', company_id),('available_for_appoint','=',True)]",
        )
    appoint_group_person_ids = fields.Many2many("res.partner", compute='_compute_appoint_group_person', string="Appointment Group Persons")
    time_slot = fields.Many2one("appointment.timeslot", "Time Slot", tracking=True, copy=False)
    person_time_slot_ids = fields.Many2many("appointment.timeslot", compute='_compute_appoint_person_timeslots', string="Appointment Persons Timeslot")
    appoint_state = fields.Selection([
        ('new', 'New'),
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('done', 'Done')], string="Appointment State", default="new", tracking=True, copy=False)
    time_from = fields.Float("Time From", related="time_slot.start_time")
    time_to = fields.Float("Time To", related="time_slot.end_time")
    time_slot_day = fields.Char("Day", compute="compute_timeslotday", store=True)
    invoice_id = fields.Many2one('account.move', 'Invoice', tracking=True, copy=False)
    invoice_status = fields.Selection(string="Invoice Status", related="invoice_id.state", copy=False)
    payment_state = fields.Selection(
        related="invoice_id.payment_state",
        string='Invoice Payment Status', copy=False,)

    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
        default=lambda self: self.env.user.company_id)
    pricelist_id = fields.Many2one(
        'product.pricelist',
        string='Pricelist',
        check_company=True,
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        help="If you change the pricelist, only newly added lines will be affected.",
        )
    currency_id = fields.Many2one(
        "res.currency", compute='_compute_currency_id',
        string="Currency", readonly=True, store=True)
    user_id = fields.Many2one(
        'res.users', string='Salesperson', index=True, tracking=2, default=lambda self: self.env.user)
    source = fields.Many2one('appointment.source', string="Source", default=set_default_source)
    enable_notify_reminder = fields.Boolean(string="Notify using Mail", default= lambda self: self.env['ir.default'].sudo()._get('res.config.settings', 'enable_notify_reminder'))
    remind_in = fields.Selection([('days', 'Day(s)'),('hours', 'Hour(s)')], string="Remind In", default="hours")
    remind_time = fields.Integer(string="Reminder Time", default=1)
    description = fields.Text("Description", copy=False)
    amount_untaxed = fields.Monetary(string='Untaxed Amount', store=True, readonly=True, compute='_amount_all', tracking=5)
    amount_tax = fields.Monetary(string='Taxes', store=True, readonly=True, compute='_amount_all')
    amount_total = fields.Monetary(string='Total', store=True, readonly=True, compute='_amount_all', tracking=4)

    is_mail_sent = fields.Boolean("Reminder Mail Send",copy=False)
    appoint_lines = fields.One2many('appointment.lines', 'appoint_id', string='Appointment Lines', copy=True, auto_join=True )
    color = fields.Integer("Color")
    reject_reason = fields.Char("Reject Reason")

    # new fields added for appointment address
    app_street1 = fields.Char("Street", compute="compute_appointment_address", store=True)
    app_street2 = fields.Char("Street2", compute="compute_appointment_address", store=True)
    app_city = fields.Char("City", compute="compute_appointment_address", store=True)
    app_zip = fields.Char("ZipCode", compute="compute_appointment_address", store=True)
    app_state_id = fields.Many2one('res.country.state'," State ", compute="compute_appointment_address", store=True)
    app_country_id = fields.Many2one('res.country', string="Country", compute="compute_appointment_address", store=True)
    app_phone = fields.Char('Mobile Number', compute="compute_appointment_address", store=True)
    app_email = fields.Char('Email Id',compute="compute_appointment_address", store=True)

    # these new fields are added to show correct time in the calendar view
    app_dt_start = fields.Datetime('Start Datetime', compute="_compute_app_dt", store=True)
    app_dt_stop = fields.Datetime('Stop Datetime', compute="_compute_app_dt", store=True)
    allday = fields.Boolean('All Day', compute="_compute_app_dt", store=True)

    def wk_convert_timezone_utc(self, appoint_datetime):
        now_utc = datetime.now(timezone('UTC'))
        if self.env.user.tz:
            now_timezone = now_utc.astimezone(timezone(self.env.user.tz))
        else:
            now_timezone = now_utc.astimezone(timezone('UTC'))
        utc_offset_timedelta = datetime.strptime(now_utc.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S") - datetime.strptime(now_timezone.strftime("%Y-%m-%d %H:%M:%S"), "%Y-%m-%d %H:%M:%S")
        local_datetime = datetime.strptime(appoint_datetime, "%Y-%m-%d %H:%M:%S")
        utc_datetime = local_datetime + utc_offset_timedelta
        return utc_datetime.strftime("%Y-%m-%d %H:%M:%S")

    @api.depends('pricelist_id', 'company_id')
    def _compute_currency_id(self):
        for appointment in self:
            appointment.currency_id = appointment.pricelist_id.currency_id or appointment.company_id.currency_id

    @api.depends("appoint_date", "time_from", "time_to", "time_slot")
    def _compute_app_dt(self):
        for rec in self:
            appoint_date = rec.appoint_date
            time_slot = rec.time_slot
            if appoint_date:
                if time_slot:
                    rec.allday = False
                    time_from = time_slot.float_time_convert(rec.time_from).split(':')
                    time_to = time_slot.float_time_convert(rec.time_to).split(':')
                    t1 = datetime(appoint_date.year, appoint_date.month, appoint_date.day, int(time_from[0]), int(time_from[1]))
                    t2 = datetime(appoint_date.year, appoint_date.month, appoint_date.day, int(time_to[0]), int(time_to[1]))
                    rec.app_dt_start = self.wk_convert_timezone_utc(str(t1))
                    rec.app_dt_stop = self.wk_convert_timezone_utc(str(t2))
                else:
                    t1 = datetime(appoint_date.year, appoint_date.month, appoint_date.day)
                    t2 = datetime(appoint_date.year, appoint_date.month, appoint_date.day)
                    rec.allday = True
                    rec.app_dt_start = self.wk_convert_timezone_utc(str(t1))
                    rec.app_dt_stop = self.wk_convert_timezone_utc(str(t2))

    @api.depends('appoint_date')
    def compute_timeslotday(self):
        for rec in self:
            if rec.appoint_date:
                day = datetime.strptime(str(rec.appoint_date) ,'%Y-%m-%d').date().strftime('%A').lower()
                days = {
                    'monday': _('Monday'),
                    'tuesday': _('Tuesday'),
                    'wednesday': _('Wednesday'),
                    'thursday': _('Thursday'),
                    'friday': _('Friday'),
                    'saturday': _('Saturday'),
                    'sunday': _('Sunday'),
                }.get(day)
                rec.update({'time_slot_day':days})

    @api.onchange('customer')
    def onchange_customer(self):
        if self.customer:
            self.update({
                'pricelist_id': self.customer.property_product_pricelist and self.customer.property_product_pricelist.id or False,
            })
            return

    @api.onchange('appoint_date')
    def _check_timeslot(self):
        if self.appoint_date and self.time_slot:
            self.time_slot = False

    @api.onchange('appoint_date')
    def compute_appdate(self):
        appoint_date = self.appoint_date
        if appoint_date:
            dt = str(appoint_date)
            d1 = datetime.strptime(str(dt),"%Y-%m-%d").date()
            d2 = date.today()
            rd = relativedelta(d2,d1)
            if rd.days > 0 or rd.months > 0 or rd.years > 0:
                raise UserError(_("Appointment date cannot be before today."))

    def apply_pricelist(self):
        return self.env['ir.default'].sudo()._get('res.config.settings', 'apply_pricelist')

    @api.model
    def get_appoint_line_details(self, appoint_person, appoint_group):
        appoint_charge = 0
        flag = 1
        name = 'Appoint Charge'
        appoint_group = self.env['appointment.person.group'].sudo().browse(int(appoint_group))
        appoint_person = self.env['res.partner'].sudo().browse(int(appoint_person))
        appoint_product = appoint_group.product_tmpl_id or False

        if appoint_person and appoint_person.appoint_person_charge > 0:
            appoint_charge = appoint_person.appoint_person_charge
            name = _("Charge for Appointment Person")
            if appoint_person.appoint_product_id:
                appoint_product = appoint_person.appoint_product_id
                if appoint_product.list_price != appoint_charge:
                    appoint_product.write({'list_price': appoint_charge})
            else:
                flag = 0

        elif appoint_group and appoint_group.group_charge > 0:
            appoint_charge = appoint_group.group_charge
            name = _("Charge for Appointment Group")
            if appoint_product and appoint_product.list_price != appoint_charge:
                appoint_product.write({'list_price': appoint_charge})

        else:
            # if appoint_person and appoint_person.appoint_person_charge <= 0 or appoint_group and appoint_group.group_charge <= 0:
            appoint_charge = 0.0
            name = _("Appointment Free of Charge")
            if appoint_product and appoint_product.list_price != appoint_charge:
                appoint_product.write({'list_price': appoint_charge})
        return appoint_product, appoint_charge, name, flag

    @api.onchange("appoint_person_id", 'appoint_group_id')
    def _compute_appoint_line(self):
        value={}
        appoint_product, appoint_charge, name, flag = self.env['appointment'].get_appoint_line_details(self.appoint_person_id.id, self.appoint_group_id.id)
        if self.appoint_lines:
            self.appoint_lines = False

        # code for applying pricelist
        if flag == 1 and appoint_charge > 0 and self.pricelist_id and self.apply_pricelist():
            appoint_charge = self.env['appointment'].get_appoint_pricelist_price(pricelist_id= self.pricelist_id.id, prod_tmpl_id= appoint_product, appoint_charge= appoint_charge)

        if self.appoint_group_id:
            prod_variant_obj = self.env['product.product'].sudo().browse(appoint_product.product_variant_id.id)
            vals = {
                'appoint_product_id': prod_variant_obj.id,
                'tax_id': [(6, 0, prod_variant_obj.sudo().taxes_id.ids)],
                'name': name,
                'price_unit': appoint_charge,
                'product_qty' : 1.0,
                'price_subtotal': appoint_charge,
            }
            value = {'value': {'appoint_lines': [(0, 0, vals)]}}
            return value

    @api.onchange('appoint_group_id')
    def compute_persons(self):
        if self.appoint_group_id:
            self.appoint_person_id = False
        if self.time_slot:
            self.time_slot = False
        if self.appoint_person_id:
            self.appoint_person_id = False

    @api.depends("appoint_group_id")
    def _compute_appoint_group_person(self):
        for rec in self:
            rec.appoint_group_person_ids = []
            if rec.appoint_group_id and rec.appoint_group_id.appoint_person_ids:
                rec.appoint_group_person_ids = rec.appoint_group_id.appoint_person_ids.ids

    @api.onchange('appoint_person_id')
    def compute_timeslots(self):
        if self.appoint_person_id and self.time_slot:
            self.time_slot = False

    @api.depends("appoint_person_id", "appoint_group_id", "appoint_date")
    def _compute_appoint_person_timeslots(self):
        for rec in self:
            rec.person_time_slot_ids = False
            if rec.appoint_date:
                selected_day = datetime.strptime(str(rec.appoint_date),'%Y-%m-%d').weekday()
                selected_day = D[selected_day]
                t2 = []
                time_slot_obj = self.env["appointment.day.slots"].search([])
                for t in time_slot_obj:
                    if t.day == selected_day and t.appointee_id.id == rec.appoint_person_id.id:
                        t2.append(t.time_slots_ids.ids)
                        t2 = t2[0]
                if not rec.appoint_person_id:
                    rec.person_time_slot_ids = t2
                else:
                    slots = self.env["appointment.timeslot"].search(['|', ('company_id', '=', False), ('company_id', '=', self.env.user.company_id.id), ('id', 'in', t2)])
                    rec.person_time_slot_ids = slots.ids if slots else False

    def send_new_appoint_mail(self):
        for rec in self:
            template_obj = self.env['mail.template']
            appoint_config_obj = self.env['res.config.settings'].get_values()
            if appoint_config_obj.get("enable_notify_customer_on_new_appoint") == True and appoint_config_obj.get("notify_customer_on_new_appoint"):
                temp_id = appoint_config_obj["notify_customer_on_new_appoint"]
                if not temp_id:
                    temp_id = self.sudo().env.ref("wk_appointment.appoint_mgmt_new_appoint_mail_to_customer")
                if temp_id:
                    template_obj.browse(temp_id).sudo().send_mail(rec.id, force_send=True)
            if appoint_config_obj.get("enable_notify_admin_on_new_appoint")==True and appoint_config_obj.get("notify_admin_on_new_appoint"):
                temp_id = appoint_config_obj["notify_admin_on_new_appoint"]
                if not temp_id:
                    temp_id = self.sudo().env.ref("wk_appointment.appoint_mgmt_new_appoint_mail_to_admin")
                if temp_id:
                    template_obj.browse(temp_id).sudo().send_mail(rec.id, force_send=True)
            if appoint_config_obj.get("enable_notify_appointee_on_new_appoint")==True and appoint_config_obj.get("notify_appointee_on_new_appoint"):
                temp_id = appoint_config_obj["notify_appointee_on_new_appoint"]
                if not temp_id:
                    temp_id = self.sudo().env.ref("wk_appointment.appoint_mgmt_new_appoint_mail_to_appointee")
                if temp_id:
                    template_obj.browse(temp_id).sudo().send_mail(rec.id, force_send=True)

    def send_approve_appoint_mail(self):
        for rec in self:
            template_obj = self.env['mail.template']
            appoint_config_obj = self.env['res.config.settings'].get_values()
            if appoint_config_obj.get("enable_notify_customer_on_approve_appoint")==True and appoint_config_obj.get("notify_customer_on_approve_appoint"):
                temp_id = appoint_config_obj["notify_customer_on_approve_appoint"]
                if not temp_id:
                    temp_id = self.sudo().env.ref("wk_appointment.appoint_mgmt_email_template_to_customer")
                if temp_id:
                    template_obj.browse(temp_id).sudo().send_mail(rec.id, force_send=True)

    def button_approve_appoint(self):
        if not self.appoint_person_id.allow_multi_appoints:
            appointment_obj = self.sudo().search([
                    ("appoint_date", '=', self.appoint_date),
                    ("appoint_person_id", '=', self.appoint_person_id.id),
                    ("time_slot", "=", self.time_slot.id),
                    ("appoint_state", "in", ['approved']),
                ])
            if appointment_obj:
                raise UserError("An appointment is already approved for this appointee on same date and time slot.")
        self.compute_appdate()
        self.write({'appoint_state': 'approved'})
        self.send_approve_appoint_mail()
        return True

    def button_set_to_pending(self):
        self.write({'appoint_state': 'pending'})
        return True

    def button_done_appoint(self):
        for rec in self:
            current_date = date.today()
            later_date = datetime.strptime(str(rec.appoint_date), "%Y-%m-%d").date()
            time_diff = relativedelta(later_date, current_date)
            if time_diff.days > 0 or time_diff.months > 0 or time_diff.years > 0:
                raise UserError(_("Appointment cannot be made Done before Appointment Date."))
            if time_diff.days == 0 and time_diff.months == 0 and time_diff.years == 0 and rec.time_slot:
                time_to = rec.time_slot.float_time_convert(rec.time_to).split(':')
                time_to = (str(time_to[0])[:2]).zfill(2) + ":" + (str(time_to[1])[:2]).zfill(2) + ":00"
                current_time = datetime.now()
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                current_time = pytz.utc.localize(current_time).astimezone(user_tz).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                current_time = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
                current_time = str(current_time).split(' ')[1]
                current_time = datetime.strptime(current_time, "%H:%M:%S")
                time_to = datetime.strptime(time_to, "%H:%M:%S")
                if current_time < time_to:
                    raise UserError(_("Appointment cannot be made Done before Slottime."))
        self.write({'appoint_state' : 'done'})
        return True

    def _prepare_invoice(self):
        self.ensure_one()
        company_id = self.customer.company_id
        journal = self.env['account.bank.statement.line'].with_company(company_id).with_context(default_type='out_invoice')._get_default_journal()
        if not journal:
            raise UserError(_('Please define an accounting sales journal for the company %s (%s).') % (company_id.name, company_id.id))

        invoice_vals = {
            'ref': self.name or '',
            'move_type': 'out_invoice',
            'narration': self.description,
            'currency_id': self.pricelist_id.currency_id.id or self.company_id.currency_id.id,
            'invoice_user_id': self.user_id and self.user_id.id,
            'partner_id': self.customer.id,
            'partner_shipping_id': self.customer.id,
            'fiscal_position_id': self.customer.property_account_position_id and self.customer.property_account_position_id.id or False,
            'invoice_origin': self.name,
            'invoice_payment_term_id': self.customer.property_payment_term_id and self.customer.property_payment_term_id.id or False,
            'invoice_line_ids': [],
        }
        return invoice_vals

    def action_view_invoice(self):
        invoices = self.mapped('invoice_id')
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        if len(invoices) > 1:
            action['domain'] = [('id', 'in', invoices.ids)]
        elif len(invoices) == 1:
            form_view = [(self.env.ref('account.view_move_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state,view) for state,view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = invoices.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        context = {
            'default_move_type': 'out_invoice',
        }
        if len(self) == 1:
            context.update({
                'default_partner_id': self.customer.id,
                'default_partner_shipping_id': self.customer.id,
                'default_invoice_origin': self.mapped('name'),
                'default_user_id': self.user_id.id,
            })
        action['context'] = context
        return action

    def button_create_invoice(self):
        self.ensure_one()
        if not self.appoint_lines:
            raise UserError(_("There are no appointment lines."))
        # if not self.pricelist_id:
        #     raise UserError(_("There is no Pricelist selected."))
        precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        invoice_vals_list = []
        for appoint in self:
            invoice_vals = appoint._prepare_invoice()
            for line in appoint.appoint_lines:
                invoice_vals['invoice_line_ids'].append((0, 0, line.prepare_appoint_invoice_line()))
        if not invoice_vals['invoice_line_ids']:
            raise UserError(_('There is no invoiceable line.'))
        invoice_vals_list.append(invoice_vals)
        moves = self.env['account.move'].with_context(default_move_type='out_invoice').create(invoice_vals_list)
        self.invoice_id = moves.id if len(moves) == 1 else moves[0].id
        for move in moves:
            move.message_post_with_source('mail.message_origin_link',
                render_values={'self': move, 'origin': move.line_ids.mapped('sale_line_ids.order_id')},
                subtype_xmlid='mail.mt_note',
            )
        return self.action_view_invoice()

    def button_reject_appoint_action(self):
        view_id = self.env["appoint.rejectreason.wizard"]
        vals = {
            'name': _("Mention reason to reject appointment"),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'appoint.rejectreason.wizard',
            'res_id': view_id.id,
            'type': "ir.actions.act_window",
            'target': 'new',
        }
        return vals

    def reject_appoint(self, add_reason):
        self.ensure_one()
        self.reject_reason = add_reason
        self.message_post(body=add_reason)
        self.write({'appoint_state': 'rejected'})
        template_obj = self.env['mail.template']
        appoint_config_obj = self.env['res.config.settings'].get_values()
        if appoint_config_obj.get("enable_notify_customer_on_reject_appoint") == True and appoint_config_obj.get("notify_customer_on_reject_appoint"):
            temp_id = appoint_config_obj["notify_customer_on_reject_appoint"]
            if not temp_id:
                temp_id = self.sudo().env.ref("wk_appointment.appoint_mgmt_reject_email_template_to_customer")
            if temp_id:
                template_obj.browse(temp_id).sudo().send_mail(self.id, force_send=True)

    def check_time_values(self, vals):
        time_from = vals.get('time_from') if vals.get('time_from') else self.time_from
        time_to = vals.get('time_to') if vals.get('time_to') else self.time_to
        if time_from:
            if time_from >= 24 or time_from < 0:
                raise UserError(_("Please enter a valid hour between 00:00 and 24:00"))
        if time_to:
            if time_to >= 24 or time_to < 0:
                raise UserError(_("Please enter a valid hour between 00:00 and 24:00"))
        if time_from and time_to:
            if time_from >= time_to:
                raise UserError(_("Please enter a valid start and end time."))

    def _check_appoint_multi_bookings(self, vals):
        for rec in self:
            if vals.get("time_slot"):
                appoint_person_id = vals.get('appoint_person_id') if vals.get('appoint_person_id') else rec.appoint_person_id
                appoint_person_obj = self.env["res.partner"].browse(int(appoint_person_id))
                time_slot_id = self.env["appointment.timeslot"].browse(vals.get("time_slot"))
                appoint_date = vals.get('appoint_date') if vals.get('appoint_date') else rec.appoint_date
                if appoint_person_obj and time_slot_id and not appoint_person_obj.allow_multi_appoints:
                    appointment_obj = self.env["appointment"].search([
                        ("appoint_date",'=', appoint_date),
                        ("appoint_person_id",'=', appoint_person_obj.id),
                        ("time_slot","=", time_slot_id.id),
                        ("appoint_state","not in", ['rejected']),
                        ("id","!=", rec.id),
                    ])
                    if appointment_obj:
                        raise UserError(_("There is already an appointment booked for this person with this timeslot. Please select any other slot." ))
        return True

    def _check_appoint_already_booked(self, vals):
        for rec in self:
            time_slot = vals.get("time_slot") if vals.get("time_slot") else rec.time_slot.id
            appoint_slot_id = self.env["appointment.timeslot"].browse(time_slot) or False
            appoint_date = vals.get('appoint_date') if vals.get('appoint_date') else rec.appoint_date
            customer = vals.get('customer') if vals.get('customer') else rec.customer.id
            if appoint_date and appoint_slot_id and customer:
                appointment_obj = self.env["appointment"].search([
                    ("appoint_date", '=', appoint_date),
                    ("customer", '=', customer),
                    ("time_slot", "=", appoint_slot_id.id),
                    ("appoint_state", "not in", ['rejected']),
                    ("id", "!=", rec.id),
                ])
                if appointment_obj:
                    raise UserError(_("There is already an appointment booked for this person with this timeslot. Please select any other slot."))
        return True

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals['name'] = self.env['ir.sequence'].sudo().next_by_code("appointment")
            if self._context.get("website_appoint"):
                vals['source'] = self.env['appointment.source'].search([('name', '=', 'Website')], limit=1).id
            self.check_time_values(vals)
            appointment = super(Appointment, self).create(vals)
            appointment.compute_appdate()
            appointment._check_appoint_time(vals)
            appointment._check_appoint_multi_bookings(vals)
            appointment._check_appoint_already_booked(vals)
            appointment.send_new_appoint_mail()
            return appointment

    def _check_appoint_time(self, vals):
        for rec in self:
            current_date = date.today()
            later_date = rec.appoint_date
            later_date = datetime.strptime(str(later_date),'%Y-%m-%d').date()
            time_diff = relativedelta(later_date, current_date)
            if vals.get("time_slot") and time_diff.days == 0 and time_diff.months == 0 and time_diff.years == 0:
                time_slot = self.env["appointment.timeslot"].browse(vals.get("time_slot"))
                time_to = time_slot.float_time_convert(time_slot.end_time).split(':')
                time_to_hour = str(time_to[0])[:2]

                minutes = int(round((time_slot.end_time % 1) * 60))
                if minutes == 60:
                    minutes = 0
                time_to_min = str(minutes).zfill(2)

                current_time = datetime.now().replace(microsecond=0).replace(second=0)
                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                current_time = pytz.utc.localize(current_time).astimezone(user_tz).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                current_time = datetime.strptime(str(current_time), '%Y-%m-%d %H:%M:%S')
                if current_time.hour > int(time_to_hour):
                    raise UserError(_("This slot time cannot be selected for today."))
                if current_time.hour == int(time_to_hour) and current_time.minute >= int(time_to_min):
                    raise UserError(_("This slot time cannot be selected for today."))
        return True

    def write(self, vals):
        for rec in self:
            if vals.get("appoint_state"):
                if rec.appoint_state == 'new' and vals.get("appoint_state") == 'done' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'pending' and vals.get("appoint_state") == 'new' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'pending' and vals.get("appoint_state") == 'done' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'rejected' and vals.get("appoint_state") == 'new' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'rejected' and vals.get("appoint_state") == 'approved' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'rejected' and vals.get("appoint_state") == 'done' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'done' and vals.get("appoint_state") == 'new' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'done' and vals.get("appoint_state") == 'pending' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'done' and vals.get("appoint_state") == 'approved' :
                    raise UserError(_('Invalid Move !!'))
                if rec.appoint_state == 'done' and vals.get("appoint_state") == 'rejected' :
                    raise UserError(_('Invalid Move !!'))
            rec.check_time_values(vals)
            res = super(Appointment, self).write(vals)
            if vals.get("appoint_date"):
                rec.compute_appdate()
            if vals.get('time_slot'):
                rec._check_appoint_time(vals)
                rec._check_appoint_already_booked(vals)
            rec._check_appoint_multi_bookings(vals)
        return res

    def send_reminder_mail_to_customer(self):
        template_obj = self.env['mail.template']
        appoint_config_obj = self.env['res.config.settings'].get_values()
        if appoint_config_obj["enable_notify_reminder"] and appoint_config_obj.get("notify_reminder_mail_template") and appoint_config_obj["notify_reminder_mail_template"]:
            temp_id = appoint_config_obj[
                "notify_reminder_mail_template"]
            if temp_id:
                template_obj.browse(temp_id).sudo().send_mail(self.id, force_send=True)
        return True

    @api.model
    def send_mail_for_reminder_scheduler_queue(self):
        obj = self.search([])
        for rec in obj:
            if rec.appoint_state == 'approved':
                if rec.enable_notify_reminder:
                    remind_time = rec.remind_time
                    if remind_time:
                        if rec.remind_in == 'days':
                            current_time = date.today()
                            later_time = datetime.strptime(str(rec.appoint_date), "%Y-%m-%d").date() - timedelta(days=remind_time)
                            time_diff = relativedelta(later_time, current_time)
                            if time_diff.days ==  0 and time_diff.months == 0 and time_diff.years == 0:
                                if not rec.is_mail_sent:
                                    rec.send_reminder_mail_to_customer()
                                    rec.is_mail_sent = True
                        else:
                            if rec.time_from:
                                time_from = rec.time_slot.float_time_convert(rec.time_from).split(':')
                                time_from = (str(time_from[0])[:2]).zfill(2) + ":" + (str(time_from[1])[:2]).zfill(2) + ":00"
                                later_time = datetime.strftime(
                                    datetime.strptime(str(rec.appoint_date) + ' ' + time_from, DEFAULT_SERVER_DATETIME_FORMAT), '%Y-%m-%d %H:%M:%S')
                                current_time = datetime.now()
                                user_tz = pytz.timezone(self.env.user.tz or 'UTC')
                                current_time = pytz.utc.localize(current_time).astimezone(user_tz).strftime(DEFAULT_SERVER_DATETIME_FORMAT)
                                current_time = datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S')
                                later_time = datetime.strptime(later_time, '%Y-%m-%d %H:%M:%S')
                                current_time = time.mktime(current_time.timetuple())
                                later_time = time.mktime(later_time.timetuple())
                                time_diff_in_mins = int(later_time - current_time ) / 60
                                remind_in_mins = rec.remind_time * 60
                                if time_diff_in_mins <= remind_in_mins:
                                    if not rec.is_mail_sent:
                                        rec.send_reminder_mail_to_customer()
                                        rec.is_mail_sent = True

    def fetch_appointee_data(self, appointee_id=None):
        all_appointees = self.env['appointment'].search([])
        is_manager_group = self.env.user.has_group('wk_appointment.appointment_manager_group')
        is_officer_group = self.env.user.has_group('wk_appointment.appointment_officer_group')
        new_appointment_count = all_appointees.filtered(lambda rec: (rec.appoint_state == 'new' and rec.appoint_person_id.id == appointee_id) if appointee_id else rec.appoint_state == 'new')
        pending_appointment_count = all_appointees.filtered(lambda rec: (rec.appoint_state == 'pending' and rec.appoint_person_id.id == appointee_id) if appointee_id else rec.appoint_state == 'pending')
        approved_appointment_count = all_appointees.filtered(lambda rec: (rec.appoint_state == 'approved' and rec.appoint_person_id.id == appointee_id) if appointee_id else rec.appoint_state == 'approved')
        rejected_appointment_count = all_appointees.filtered(lambda rec: (rec.appoint_state == 'rejected' and rec.appoint_person_id.id == appointee_id) if appointee_id else rec.appoint_state == 'rejected')
        completed_appointment_count = all_appointees.filtered(lambda rec: (rec.appoint_state == 'done' and rec.appoint_person_id.id == appointee_id) if appointee_id else rec.appoint_state == 'done')
        filtered_data = {}
        all_appointees_list = []
        for record in all_appointees:
            details = {
                    'id': record.appoint_person_id.id,
                    'name': record.appoint_person_id.name,

                }
            if details not in all_appointees_list:
                all_appointees_list.append(details)
        filtered_data.update({
            'is_manager': is_manager_group,
            'is_officer': is_officer_group,
            'appointee_list': all_appointees_list,
            'new_appointment_count': len(new_appointment_count),
            'pending_appointment_count': len(pending_appointment_count),
            'approved_appointment_count': len(approved_appointment_count),
            'rejected_appointment_count': len(rejected_appointment_count),
            'completed_appointment_count': len(completed_appointment_count),
        })
        return filtered_data

    def get_appointment_status_data(self, post):
        """
        Get appointment counts on the basis of their appointement states
        """
        appointee_id = post.get('appointee_id')
        appointment_condition = f"appoint_person_id = {appointee_id}" if appointee_id else ""
        status_counts = {status: 0 for status in ["new", "approved", "pending", "completed", "rejected"]}
        appointment_data = self._get_appointments_query_result(appointment_condition, appointee_id)
        for status, count in appointment_data:
            if status in status_counts:
                status_counts[status] += count
        return {
            'status_counts': status_counts,
        }

    def get_appointee_list(self, post):
        appointee_id = post.get('appointee_id')
        # Query for all appointments and calculate total earnings
        all_appointments = self.env['appointment'].search([])
        appointee_list = []
        for record in self.env['appointment'].search([]):
            details = {
                'id': record.appoint_person_id.id,
                'name': record.appoint_person_id.name,
            }
            if details not in appointee_list:
                appointee_list.append(details)
        return {
            "appointee_list": appointee_list,
        }

    # Define a helper function to fetch earnings using SQL query
    def fetch_earnings(self, query, params):
        self.env.cr.execute(query, params)
        result = self.env.cr.fetchall()
        # We need to check here if the appointment earning result is not None,
        if result[0][0]:
            return sum(record[0] for record in result)
        return False

    def get_earnings_by_interval(self, period, current_date, appointee_id):
        """
        This function returns the total earnings for the given time period: week, month, or year.
        It uses SQL queries to calculate earnings instead of the search function.
        """
        earnings_data = []
        if period == 'Weekly':
            # For weekly earnings, we want the current week's earnings (Monday to Sunday).
            start_date = current_date - timedelta(days=current_date.weekday())
            start_date = start_date.date()  # Strip the time component from the date.
            end_date = start_date + timedelta(days=6)  # End of the current week (Sunday)
            for i in range(7):
                day_date = start_date + timedelta(days=i)

                # Modify the SQL query to handle the case where appointee_id is not passed
                if appointee_id:
                    query = """
                        SELECT SUM(a.price_total)
                        FROM appointment_lines a
                        JOIN appointment app ON app.id = a.appoint_id
                        JOIN account_move inv ON inv.id = app.invoice_id
                        WHERE inv.invoice_date >= %s
                        AND inv.invoice_date < %s
                        AND app.appoint_person_id = %s
                        AND inv.payment_state = 'paid'
                    """
                    params = (day_date, day_date + timedelta(days=1), appointee_id)
                else:
                    query = """
                        SELECT SUM(a.price_total)
                        FROM appointment_lines a
                        JOIN appointment app ON app.id = a.appoint_id
                        JOIN account_move inv ON inv.id = app.invoice_id
                        WHERE inv.invoice_date >= %s
                        AND inv.invoice_date < %s
                        AND inv.payment_state = 'paid'
                    """
                    params = (day_date, day_date + timedelta(days=1))
                total_earnings = self.fetch_earnings(query, params)
                earnings_data.append(total_earnings)

        elif period == 'Monthly':
            # For monthly earnings, we want the earnings for each month.
            for month in range(1, 13):  # From January (1) to December (12)
                start_date = current_date.replace(year=current_date.year, month=month, day=1)
                if month == 12:
                    end_date = datetime(current_date.year + 1, 1, 1) - timedelta(days=1)  # End of December
                else:
                    end_date = (start_date.replace(month=month + 1) - timedelta(days=1))  # End of the current month

                # Modify the SQL query to handle the case where appointee_id is not passed
                if appointee_id:
                    query = """
                        SELECT SUM(a.price_total)
                        FROM appointment_lines a
                        JOIN appointment app ON app.id = a.appoint_id
                        JOIN account_move inv ON inv.id = app.invoice_id
                        WHERE inv.invoice_date >= %s
                        AND inv.invoice_date <= %s
                        AND app.appoint_person_id = %s
                        AND inv.payment_state = 'paid'
                    """
                    params = (start_date, end_date, appointee_id)
                else:
                    query = """
                        SELECT SUM(a.price_total)
                        FROM appointment_lines a
                        JOIN appointment app ON app.id = a.appoint_id
                        JOIN account_move inv ON inv.id = app.invoice_id
                        WHERE inv.invoice_date >= %s
                        AND inv.invoice_date <= %s
                        AND inv.payment_state = 'paid'
                    """
                    params = (start_date, end_date)
                total_earnings = self.fetch_earnings(query, params)
                earnings_data.append(total_earnings)

        elif period == 'Yearly':
            # For yearly earnings, we want the earnings for each year.
            for year in range(current_date.year - 10, current_date.year + 1):
                start_date = datetime(year, 1, 1).date()  # Start of the year (ensure it's a date)
                end_date = datetime(year, 12, 31).date()  # End of the year (ensure it's a date)

                # Modify the SQL query to handle the case where appointee_id is not passed
                if appointee_id:
                    query = """
                        SELECT SUM(a.price_total)
                        FROM appointment_lines a
                        JOIN appointment app ON app.id = a.appoint_id
                        JOIN account_move inv ON inv.id = app.invoice_id
                        WHERE inv.invoice_date >= %s
                        AND inv.invoice_date <= %s
                        AND app.appoint_person_id = %s
                        AND inv.payment_state = 'paid'
                    """
                    params = (start_date, end_date, appointee_id)
                else:
                    query = """
                        SELECT SUM(a.price_total)
                        FROM appointment_lines a
                        JOIN appointment app ON app.id = a.appoint_id
                        JOIN account_move inv ON inv.id = app.invoice_id
                        WHERE inv.invoice_date >= %s
                        AND inv.invoice_date <= %s
                        AND inv.payment_state = 'paid'
                    """
                    params = (start_date, end_date)
                total_earnings = self.fetch_earnings(query, params)
                earnings_data.append(total_earnings)
        else:
            return 0  # If no valid period is passed, return 0
        return earnings_data

    def _get_appointments_query_result(self, appointment_condition, appointee_id):
        """
            Query to get appointments count for all statuses without any time-based filter.
        """

        if appointee_id:
            query = f"""
                SELECT appoint_state, COUNT(*) AS total_appointments
                FROM appointment
                WHERE {appointment_condition}
                GROUP BY appoint_state
            """
        else:
            query = f"""
                SELECT appoint_state, COUNT(*) AS total_appointments
                FROM appointment
                GROUP BY appoint_state
            """
        self.env.cr.execute(query)
        return self.env.cr.fetchall()


class AppointmentLines(models.Model):
    _name = 'appointment.lines'
    _description = "Appointment Lines"

    @api.depends('product_qty', 'price_unit', 'tax_id')
    def compute_line_total(self):
        """
        Compute the amounts of the Appointment line.
        """
        for line in self:
            price = line.price_unit
            taxes = line.tax_id.compute_all(price, line.appoint_id.currency_id, line.product_qty, product=line.appoint_product_id, partner=line.appoint_id.customer)
            line.update({
                'price_tax': sum(t.get('amount', 0.0) for t in taxes.get('taxes', [])),
                'price_total': taxes['total_included'],
                'price_subtotal': taxes['total_excluded'],
            })

    appoint_id = fields.Many2one('appointment', string="Appointment Reference", required=True ,
        ondelete ='cascade', index=True, copy=False)
    name = fields.Text(string='Description', required=True)
    appoint_product_id = fields.Many2one('product.product', string='Product',
        domain = lambda self: [('id','in',self.env['ir.default'].sudo()._get('res.config.settings', 'appoint_product_ids'))])
    product_qty = fields.Float(string='Quantity', digits='Product Unit of Measure',
        required=True, default=1.0)
    tax_id = fields.Many2many('account.tax', string='Taxes')
    price_unit = fields.Float('Unit Price', required=True, digits='Product Price', default=0.0)
    price_subtotal = fields.Float(compute='compute_line_total', string='Subtotal', readonly=True, store=True)
    price_tax = fields.Float(compute='compute_line_total', string='Tax', readonly=True, store=True)
    price_total = fields.Float(compute='compute_line_total', string='Total', readonly=True, store=True)
    company_id = fields.Many2one(related='appoint_id.company_id', string='Company', store=True, readonly=True)

    @api.onchange('appoint_product_id')
    def product_id_change(self):
        self.name = self.appoint_product_id.name
        vals = {}
        if self.appoint_product_id:
            product = self.appoint_product_id
            name = product._compute_display_name()
            if product.description_sale:
                name += '\n' + product.description_sale
                vals['name'] = name
            if product.taxes_id:
                vals['tax_id'] = product.taxes_id
            vals['price_unit'] = self.appoint_product_id.lst_price
            if self.appoint_id.pricelist_id:
                vals['price_unit'] = self.appoint_product_id.with_context(pricelist=self.appoint_id.pricelist_id.id).list_price
        self.update(vals)

    def prepare_appoint_invoice_line(self):
        self.ensure_one()
        return {
            'name': self.name,
            'product_id': self.appoint_product_id.id,
            'product_uom_id': self.appoint_product_id.uom_id and self.appoint_product_id.uom_id.id,
            'quantity': self.product_qty,
            'price_unit': self.price_unit,
            'tax_ids': [(6, 0, self.tax_id.ids)],
        }
