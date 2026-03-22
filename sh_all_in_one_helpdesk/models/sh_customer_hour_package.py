# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from datetime import date,datetime,timedelta


class ShCustomHourPackage(models.Model):
    _name = "sh.customer.hour.package"
    _description = "Customer Hour Package"

    name = fields.Char()
    partner_id = fields.Many2one('res.partner', 'Customer')
    sh_package_date = fields.Date(string='Package Date',default=fields.Date.today)
    sh_package_date_end = fields.Date(string='Package Date End ',default=fields.Date.today)
    sh_initial_allocated_hours = fields.Float(string='Initial Allocated Hours')
    sh_rolled_over_hours = fields.Float(string='Rolled Over Hours')
    sh_total_allocated_hours = fields.Float(string='Total Allocated Hours')
    sh_hours_consumed = fields.Float(string='Hours Consumed',compute='_compute_sh_hours_consumed')
    sh_remaining_hours_at_month_end = fields.Float(string='Remaning Hours at Month End',compute='_compute_sh_hours_consumed')
    state = fields.Selection(string='State', selection=[('open', 'Open'), ('close', 'Close'),],default='open')

    @api.constrains('sh_initial_allocated_hours')
    def _check_initial_allocated_hours(self):
        for rec in self:
            if rec.sh_initial_allocated_hours <= 0:
                raise ValidationError("Initial Allocated Hours must be greater than or equal to 0.")


    @api.onchange('sh_package_date')
    def _onchange_sh_package_date(self):
        """Update end date in form view when user changes start date"""
        if self.sh_package_date:
            self.sh_package_date_end = self.sh_package_date + timedelta(days=30)

    def _compute_sh_hours_consumed(self):
        for package in self:
            package.sh_hours_consumed=0
            package.sh_remaining_hours_at_month_end=package.sh_total_allocated_hours
            if package.state=='open':
                timesheet_hours=sum(self.env['account.analytic.line'].search([('partner_id','=',package.partner_id.id),('sh_customer_hour_package_id','=',package.id),('date', '>=', package.sh_package_date),
                    ('date', '<=', package.sh_package_date_end)]).mapped('unit_amount'))
                package.sh_hours_consumed=timesheet_hours
                if timesheet_hours<package.sh_total_allocated_hours:
                    package.sh_remaining_hours_at_month_end-=timesheet_hours
                else:
                    package.sh_remaining_hours_at_month_end=0


    @api.onchange('sh_initial_allocated_hours','sh_rolled_over_hours')
    def _onchange_ah_allocated_total_hours(self):
        if self.sh_initial_allocated_hours:
            self.sh_total_allocated_hours=self.sh_initial_allocated_hours
        if self.sh_rolled_over_hours:
            self.sh_total_allocated_hours+=self.sh_rolled_over_hours



    @api.onchange('partner_id','sh_package_date')
    def _onchange_partner_id(self):
        if self.partner_id and self.sh_package_date:
            date_obj = datetime.strptime(str(self.sh_package_date), "%Y-%m-%d")
            month_year = date_obj.strftime("%B %Y")
            self.name = f"{self.partner_id.name} - {month_year}"
            self.sh_initial_allocated_hours=self.partner_id.sh_allocated_hours

    def write(self, vals):
        res = super().write(vals)
        if 'sh_package_date' in vals:
            for rec in self:
                rec._onchange_sh_package_date()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        rec = super().create(vals_list)
        for vals in vals_list:
            if 'sh_package_date' in vals:
                rec._onchange_sh_package_date()
        return rec

    @api.model
    def _run_auto_create_customer_hour_package(self):
        today = date.today()
        yesterday = date.today() - timedelta(days=1)
        # allocated_hours=self.env.company.sh_allocated_hours
        packages=self.search([('sh_package_date_end','=',yesterday),('state','=','open')])
        if packages:
            for package in packages:
                allocated_hours=package.partner_id.sh_allocated_hours
                package_id=self.env['sh.customer.hour.package'].create({
                    'partner_id':package.partner_id.id,
                    'sh_package_date':today,
                    'sh_package_date_end':today + timedelta(days=30),
                    'sh_initial_allocated_hours':allocated_hours,
                    'sh_rolled_over_hours':package.sh_remaining_hours_at_month_end,
                })
                package_id._onchange_ah_allocated_total_hours()
                package_id._onchange_partner_id()
                package.state='close' #close old package
