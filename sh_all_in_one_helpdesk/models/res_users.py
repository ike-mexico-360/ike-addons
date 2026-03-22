# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api
from odoo.http import request


class ResUsers(models.Model):
    _inherit = 'res.users'

    sh_portal_user = fields.Boolean(
        string='Portal', compute='_compute_sh_portal_user', search='_search_sh_portal_user')
    sh_portal_user_access = fields.Selection([('user', 'Portal Support User'), (
        'manager', 'Portal Manager')], string='Portal Access')
    sign = fields.Text('Signature')

    @api.depends('groups_id')
    def _compute_sh_portal_user(self):
        if self:
            for rec in self:
                if self.env.ref('base.group_portal').id in rec.groups_id.ids:
                    rec.sh_portal_user = True
                else:
                    rec.sh_portal_user = False

    def _search_sh_portal_user(self, operator, value):
        user_obj = self.env['res.users']
        domain = []
        domain.append(('sh_portal_user', operator, value))
        users = user_obj.search(domain).ids
        if users:
            return [('id', 'in', users)]
        else:
            return []
        
    # Notification
    sh_create_new_ticket_notification = fields.Boolean(string='New Ticket Notification?')
    sh_assign_ticket_notification = fields.Boolean(string='Ticket Assigned Notification?')
    sh_ticket_done_notification = fields.Boolean(string='Ticket Done Notification?')
    sh_ticket_cancel_notification = fields.Boolean(string='Ticket Cancel Notification?')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ['sign', 'sh_create_new_ticket_notification', 'sh_assign_ticket_notification', 'sh_ticket_done_notification', 'sh_ticket_cancel_notification']
    
    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ['sign', 'sh_create_new_ticket_notification', 'sh_assign_ticket_notification', 'sh_ticket_done_notification', 'sh_ticket_cancel_notification']

    # Systray Notification
    @api.model
    def systray_get_notifications(self):
        notifications = self.env['sh.user.push.notification'].search([('user_id','=',self.env.uid)],limit=25, order='msg_read,id desc')
        unread_notifications = self.env['sh.user.push.notification'].search([('user_id','=',self.env.uid),('msg_read','=',False)])
        data_notifications = []
        for notification in notifications:
            data_notifications.append({
                'id':notification.id,
                'desc':notification.description,
                'name':notification.name,
                'user_id':notification.user_id,
                'datetime':notification.datetime,
                'uid':notification.user_id.id,
                'res_model':notification.res_model,
                'res_id':notification.res_id,
                'msg_read':notification.msg_read ,
                })

        return list(data_notifications), len(unread_notifications)
    
    @api.model
    def systray_get_all_notifications(self):
        notifications = self.env['sh.user.push.notification'].search([('user_id','=',self.env.uid)],order='msg_read,id desc')
        unread_notifications = self.env['sh.user.push.notification'].search([('user_id','=',self.env.uid),('msg_read','=',False)])
        data_notifications = []
        for notification in notifications:
            data_notifications.append({
                'id':notification.id,
                'desc':notification.description,
                'name':notification.name,
                'user_id':notification.user_id,
                'datetime':notification.datetime,
                'uid':notification.user_id.id,
                'res_model':notification.res_model,
                'res_id':notification.res_id,
                'msg_read':notification.msg_read,
                })

        return list(data_notifications), len(unread_notifications)
    
class Http(models.AbstractModel):
    _inherit = 'ir.http'
    
    def session_info(self):
        info = super().session_info()
        user = request.env.user
        info["sign"] = user.sign
        info["sh_create_new_ticket_notification"] = user.sh_create_new_ticket_notification
        info["sh_assign_ticket_notification"] = user.sh_assign_ticket_notification
        info["sh_ticket_done_notification"] = user.sh_ticket_done_notification
        info["sh_ticket_cancel_notification"] = user.sh_ticket_cancel_notification
        return info

