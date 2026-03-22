# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

import datetime
from odoo import fields, models,_

class ShHelpdeskTeamInfo(models.Model):
    _name="sh.helpdesk.ticket.stage.info"
    _description="Helpdesk Task Information"

    stage_task_id = fields.Many2one("sh.helpdesk.ticket",string="Stage task")
    stage_name=fields.Char(string="Stage Name")
    date_in=fields.Datetime(string="Date In")
    date_in_by=fields.Many2one("res.users",string="Date In By")
    date_out=fields.Datetime(string="Date Out")
    date_out_by=fields.Many2one("res.users",string="Date Out By")
    day_diff=fields.Integer(string="Day Diff")
    time_diff=fields.Float(string="Time Diff")
    total_time_diff=fields.Float(string="Total Time Diff")

class HelpdeskTeamInherit(models.Model):
    _inherit="sh.helpdesk.ticket"

    helpdesk_stage_history_line=fields.One2many("sh.helpdesk.ticket.stage.info",'stage_task_id',string="Stage History Line")

    def write(self, vals):
        res = super(HelpdeskTeamInherit, self).write(vals)
        
        if vals.get('stage_id'):
            # for update record=====================
            last_create_id=self.helpdesk_stage_history_line.ids
            if last_create_id:
                previous_id=self.env['sh.helpdesk.ticket.stage.info'].browse(last_create_id[-1])
                sub_time = datetime.datetime.now() - previous_id.date_in

                # for days difference
                day_diff=sub_time.days

                # for hours difference
                test = str(sub_time.seconds//3600) +':'+ str(((sub_time.seconds//60)%60))
                vals = test.split(':')
                t, hours = divmod(float(vals[0]), 24)
                t, minutes = divmod(float(vals[1]), 60)
                minutes = minutes / 60.0
                time_to_fl =  hours + minutes

                # for total time count
                if day_diff>0:
                    test = str(sub_time.seconds//3600) +':'+ str(((sub_time.seconds//60)%60))
                    vals = test.split(':')
                    t, hours = divmod(float(vals[0]), 24)
                    t, minutes = divmod(float(vals[1]), 60)
                    minutes = minutes / 60.0
                    hours+=day_diff*24
                    total_time_to_fl =  hours + minutes
                else:
                    total_time_to_fl=time_to_fl

                stage_history={
                        'date_out':  datetime.datetime.now(),
                        'date_out_by': self.env.user,
                        'day_diff':day_diff,
                        'time_diff':time_to_fl,
                        'total_time_diff':total_time_to_fl,
                    }

                self.helpdesk_stage_history_line = [(1,last_create_id[-1],stage_history)]
                
          # for new record====================
            stage_history={
                        'stage_task_id': self.id,
                        'stage_name': self.stage_id.name,
                        'date_in': datetime.datetime.now(),
                        'date_in_by': self.env.user.id,
                    }
            self.helpdesk_stage_history_line = [(0,0,stage_history)]
        return res
