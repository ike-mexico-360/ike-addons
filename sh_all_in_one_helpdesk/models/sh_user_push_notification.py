# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.
from odoo import fields, models, api, _

class UserPushNotification(models.Model):
    _name = 'sh.user.push.notification'
    _description = "User Notification"
    _order = 'msg_read,id desc'

    user_id = fields.Many2one("res.users",string="User")
    name = fields.Char("Title")
    description = fields.Text("Description")
    datetime = fields.Datetime("Time")
    res_model = fields.Char("Res Model")
    res_id = fields.Integer("Res ID")
    msg_read = fields.Boolean("Read ?")

    @api.model
    def has_bell_notification_enabled(self):
        has_bell_notification_enabled = False
        # if self.env.company.enable_bell_notification:
        has_bell_notification_enabled = True
        result = {
            'has_bell_notification_enabled':has_bell_notification_enabled,
            }
        return result

    def open_record(self):
        self.write({'msg_read':True})
        if self.res_model:
            return {
                'name':self.name,
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': self.res_model,
                'res_id':self.res_id,
                'target': 'current',
            }
           
        

    def create_user_notification(self,user='',name='',description='',res_model='',res_id=''):
        self.env['bus.bus']._sendone(user.partner_id,
        'sh.user.push.notifications', {})
        self.env['sh.user.push.notification'].create({
            'user_id': user.id,
            'name':name,
            'description':description,
            'datetime':fields.Datetime.now(),
            'res_model':res_model,
            'res_id':res_id,
            'msg_read':False,
        })

