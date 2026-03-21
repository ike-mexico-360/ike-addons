# -*- coding: utf-8 -*-

from odoo import models, fields, api


# ! REMOVE_ME
# ToDo: REMOVE_ME
class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_qty_period = fields.Integer(string='Cantidad periodo')
    x_unit_period = fields.Selection(
        [("day", "Día(s)"), ("week", "Semana(s)"), ("month", "Mes(es)"), ("year", "Año(s)")],
        default='day', string="Periodicidad")
    x_qty_reset_period = fields.Integer(string='Reseteo contador')
    x_unit_reset_period = fields.Selection(
        [("day", "Día(s)"), ("week", "Semana(s)"), ("month", "Mes(es)"), ("year", "Año(s)")],
        default='day', string="Periodicidad reseteo contador")
    x_date_reset = fields.Date(string='Fecha de Reseteo')
    x_cl_sub_service = fields.Integer('CL Sub Service')
