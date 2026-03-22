# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import models, fields, api
from odoo.http import request
from datetime import date, timedelta
from datetime import datetime
from odoo.osv import expression
from collections import defaultdict
from dateutil.relativedelta import relativedelta
# from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import json


class TicketDashboard(models.Model):
    _name = 'ticket.dashboard'
    _description = 'Ticket Dashboard'

    name = fields.Char('Name')

    @api.model
    def get_users(self):
        users = self.env['res.users'].search_read(domain=[('share', '=', False)],fields=['id', 'name','email'])
        return users

    @api.model
    def get_user_group(self):
        dic = {}
        support_user = self.env.user.has_group(
            'sh_all_in_one_helpdesk.helpdesk_group_user')
        team_leader = self.env.user.has_group(
            'sh_all_in_one_helpdesk.helpdesk_group_team_leader')
        manager = self.env.user.has_group(
            'sh_all_in_one_helpdesk.helpdesk_group_manager')
        if support_user and not team_leader and not manager:
            dic.update({
                'user': '1'
            })
        elif support_user and team_leader and not manager:
            dic.update({
                'leader': '1'
            })
        elif support_user and team_leader and manager:
            dic.update({
                'manager': '1'
            })
        return json.dumps(dic)


    @api.model
    def get_ticket_dashboard_count(self):
        uid = request.session.uid
        user = request.env['res.users'].browse(uid)
        cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
        cids = [int(cid) for cid in cids.split(',')]
        return self.env['ir.ui.view'].with_context()._render_template('sh_all_in_one_helpdesk.ticket_dashboard_count', {
            'data_dict': {},
        })

    @api.model
    def get_ticket_counter_data(self, team_leader, team, assign_user, filter_date, start_date, end_date):
        """
        Purpose:
        This function, get_ticket_counter_data, is designed to fetch ticket counts based on different parameters for a helpdesk dashboard. 
        It queries the sh.helpdesk.ticket model and organizes the data by stages, providing a master dictionary for rendering on the dashboard.

        Parameters:
        - team_leader: Team leader's name for filtering tickets.
        - team: Team identifier for ticket filtering.
        - assign_user: Assigned user's ID for filtering tickets.
        - filter_date: Filter date option ('custom' or predefined).
        - start_date: Start date for custom date filtering.
        - end_date: End date for custom date filtering.

        Returns:
        A master dictionary containing ticket counts organized by stages, ready for rendering on the helpdesk dashboard.

        Note:
        - The function uses the sh.helpdesk.ticket and helpdesk.stages models.
        - The master dictionary structure: {stage_name: [ticket_ids]}.
        """

        configure_stages = self.env.company.dashboard_filter
        master_dictionary = {}
        color_dict = {}

        for each_stage in configure_stages:
            domain = []

            if team_leader:
                domain.append(('team_head', '=', team_leader))
            if team:
                domain.append(('team_id', '=', team))
            if assign_user:
                domain.append(('user_id', '=', assign_user))

            domain.append(('stage_id', '=', each_stage.id))

            if filter_date == 'custom' and not (start_date and end_date):
                start_date = end_date = False
            elif filter_date and filter_date != 'custom':
                start_date, end_date = self.generate_start_end_date(option=filter_date)

            if isinstance(start_date, str) and isinstance(end_date, str):
                start_date = datetime.strptime(start_date, "%m/%d/%Y").replace(hour=0, minute=0, second=0)
                end_date = datetime.strptime(end_date, "%m/%d/%Y").replace(hour=23, minute=59, second=59)
                domain.append(('create_date', '>=', start_date))
                domain.append(('create_date', '<=', end_date))

            tickets = self.env['sh.helpdesk.ticket'].search(domain)
            master_dictionary[each_stage.name] = [tickets.ids]
            color_dict[each_stage.name] = each_stage.color if each_stage.color else "#445ee9"

        return master_dictionary,color_dict

       
    
    @api.model
    def get_team(self):
        return [{'id': team.id, 'name': team.name} for team in self.env['sh.helpdesk.team'].search([])]

    def generate_start_end_date(self,option):
        today = datetime.now()  # replace with the actual current date

        if option == "today":
            start_date = end_date = today
        elif option == "yesterday":
            start_date = end_date = today - timedelta(days=1)
        elif option == "weekly":
            start_date = today - timedelta(days=today.weekday())
            end_date = today
        elif option == "prev_week":
            start_date = (today - timedelta(days=today.weekday())) - timedelta(days=7)
            end_date = today - timedelta(days=today.weekday() + 1)
        elif option == "monthly":
            start_date = date(today.year, today.month, 1)
            end_date = today
        elif option == "prev_month":
            first_day_prev_month = date(today.year, today.month, 1) - timedelta(days=1)
            start_date = date(first_day_prev_month.year, first_day_prev_month.month, 1)
            end_date = first_day_prev_month
        elif option == "cur_year":
            start_date = date(today.year, 1, 1)
            end_date = today
        elif option == "prev_year":
            start_date = date(today.year - 1, 1, 1)
            end_date = date(today.year - 1, 12, 31)
        else:
            start_date = end_date = today  # Default to today if no valid option is provided
            
        return start_date.strftime("%m/%d/%Y"), end_date.strftime("%m/%d/%Y")

    @api.model
    def get_ticket_table_data(
        self, team_leader, team, assign_user, filter_date,
        start_date, end_date, limit, offset, stage_id
    ):
        """
            Purpose:
            This function, get_ticket_table_data, is designed to fetch and organize ticket data for a helpdesk dashboard. 
            It takes various parameters such as team leader, team, assigned user, date filters, and stage ID to filter and present ticket information in a structured format. 
            The function performs queries on the sh.helpdesk.ticket model, manipulates the data, and prepares a master list for rendering on the dashboard. Additionally, 
            it adds a touch of humor to certain comments for an enjoyable coding experience.

            Parameters:
            - team_leader: Team leader's name for filtering tickets.
            - team: Team identifier for ticket filtering.
            - assign_user: Assigned user's ID for filtering tickets.
            - filter_date: Filter date option ('custom' or predefined).
            - start_date: Start date for custom date filtering.
            - end_date: End date for custom date filtering.
            - limit: Maximum number of records to fetch.
            - offset: Number of records to skip.
            - stage_id: Stage identifier for filtering tickets by stage.

            Returns:
            A master list containing structured ticket data organized by stages, ready for rendering on the helpdesk dashboard.

            Note:
            - The function uses the sh.helpdesk.ticket and helpdesk.stages models.
            - Humorous comments have been added to bring a smile to the coding journey.
        """

        domain = []

        if team_leader:
            domain.append(('team_head', '=', team_leader))  # The team leader leading the way!
        if team:
            domain.append(('team_id', '=', team))  # Team, assemble!
        if assign_user:
            domain.append(('user_id', '=', assign_user))  # Finding the chosen one!
        if stage_id:
            domain.append(('stage_id', '=', stage_id))  # Stage presence!

        if filter_date == 'custom' and not (start_date and end_date):
            start_date = end_date = False  # Time travelers not allowed without dates!
        elif filter_date and filter_date != 'custom':
            start_date, end_date = self.generate_start_end_date(option=filter_date)

        if start_date and end_date:
            start_date = datetime.strptime(start_date, "%m/%d/%Y").replace(hour=0, minute=0, second=0)
            end_date = datetime.strptime(end_date, "%m/%d/%Y").replace(hour=23, minute=59, second=59)
            domain.append(('create_date', '>=', start_date))
            domain.append(('create_date', '<=', end_date))

        tickets = self.env['sh.helpdesk.ticket'].search(domain, limit=limit, offset=offset)
        # count_tickets = self.env['sh.helpdesk.ticket'].search_count(domain)

        read_group_result = self.env['sh.helpdesk.ticket'].read_group(
            domain, ['stage_id'], ['stage_id'], lazy=False)
        
        for each_read_group in read_group_result:
            if 'stage_id' in each_read_group and each_read_group['stage_id'] == False:
                read_group_result.remove(each_read_group)
        map_read_group_result = {(res['stage_id'][0]): res['__count'] for res in read_group_result if res['stage_id'][1]}

        available_stages = tickets.mapped('stage_id').ids
        all_stages = self.env['helpdesk.stages'].search([]).ids
        remain_stages = [stage for stage in all_stages if stage not in available_stages]

        ticket_data = defaultdict(list)
        max_records_per_stage = 8
        if limit:
            max_records_per_stage = limit

        for ticket in tickets:
            ticket_stage_id = ticket.stage_id.id
            if len(ticket_data[ticket_stage_id]) < max_records_per_stage:
                ticket_data[ticket_stage_id].append(ticket)

        if remain_stages and not stage_id:
            for each_stage in remain_stages:
                ticket_data[each_stage].append([])  # Empty seats for the missing tickets!

        if stage_id and not tickets:
            ticket_data[stage_id].append([])  # The solo act on an empty stage!

        reference = [
            {stage_id: ticket_data[stage_id]} for stage_id in ticket_data
        ]

        master_list = []
        stage_model = self.env['helpdesk.stages']



        for each in reference:
            each_stage_id = next(iter(each.keys()), None)
            stage_name = stage_model.browse(each_stage_id).name
            # for stage in self.env.company.dashboard_tables:
            if each_stage_id in self.env.company.dashboard_tables.ids:
                ticket_data_list = [
                    [
                        t.name, t.partner_id.name, t.mobile_no or '',
                        t.create_date, t.write_date, t.user_id.name or '', t.id,
                        self.env.user.id,t.ticket_read_data# Login user id and ticket_read_data
                    ] if t else False for t in each.get(each_stage_id, [])
                ]
                each_table_data = {
                    'stage_id': each_stage_id,
                    'stage_name': stage_name,
                    'count_tickets':map_read_group_result.get(each_stage_id,0),
                    'ticket_data': ticket_data_list
                }
                master_list.append(each_table_data)


        return master_list

    @api.model
    def get_mobile_no(self, partner_id):
        dic = {}
        if partner_id and partner_id != 'select_partner':
            partner_id = request.env['res.partner'].browse(
                int(partner_id))
            if partner_id and partner_id.mobile:
                dic.update({
                    'mobile': str(partner_id.mobile)
                })
                
        return json.dumps(dic)

    @api.model
    def send_by_whatsapp(self, partner_id, mobile_no, message):
        dic = {}
        if partner_id and partner_id == 'select_partner':
            dic.update({
                'msg': 'Partner is Required.'
            })
        elif mobile_no and mobile_no == '':
            dic.update({
                'msg': 'Mobile Number is Required.'
            })
        elif message and message == '':
            dic.update({
                'msg': 'Message is Required.'
            })
        else:
            dic.update({
                'url': str("https://web.whatsapp.com/send?l=&phone="+mobile_no+"&text=" + message)
            })
        return json.dumps(dic)

    @api.model
    def open_tickets(self, **kw):
        dashboard_id = self.env['ticket.dashboard'].search(
            [('id', '=', 1)], limit=1)
        dashboard_id.get_ticket_data(kw.get('ids'))
        dic = {}
        dic.update({'success': 1})
        return json.dumps(dic)

    


# # -*- coding: utf-8 -*-
# # Part of Softhealer Technologies.

# from odoo import models, fields, api
# from odoo.http import request
# from datetime import datetime
# from dateutil.relativedelta import relativedelta
# from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
# import json


# class TicketDashboard(models.Model):
#     _name = 'ticket.dashboard'
#     _description = 'Ticket Dashboard'

#     name = fields.Char('Name')

#     @api.model
#     def get_user_group(self):
#         dic = {}
#         support_user = self.env.user.has_group(
#             'sh_all_in_one_helpdesk.helpdesk_group_user')
#         team_leader = self.env.user.has_group(
#             'sh_all_in_one_helpdesk.helpdesk_group_team_leader')
#         manager = self.env.user.has_group(
#             'sh_all_in_one_helpdesk.helpdesk_group_manager')
#         if support_user and not team_leader and not manager:
#             dic.update({
#                 'user': '1'
#             })
#         elif support_user and team_leader and not manager:
#             dic.update({
#                 'leader': '1'
#             })
#         elif support_user and team_leader and manager:
#             dic.update({
#                 'manager': '1'
#             })
#         return json.dumps(dic)

#     @api.model
#     def get_team_leader(self):
#         uid = request.session.uid
#         user = request.env['res.users'].browse(uid)
#         cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
#         cids = [int(cid) for cid in cids.split(',')]
#         domain = [
#             ('company_ids', 'in', cids),
#             ('share','=',False)
#         ]
#         team_heads = self.env['sh.helpdesk.team'].search([]).mapped('team_head').ids
#         domain.append(('id','in',team_heads))
#         users = self.env['res.users'].search_read(domain)
#         return users

#     @api.model
#     def get_team(self,team_leader):
#         if team_leader:
#             teams = self.env['sh.helpdesk.team'].search_read([('team_head','=',int(team_leader))])
#             return teams

#     @api.model
#     def get_team_members(self,team):
#         if team:
#             members = self.env['sh.helpdesk.team'].search([('id','=',int(team))]).mapped('team_members').ids
#             domain = [('id','in',members)]
#             members = self.env['res.users'].search_read(domain)
#             return members

#     @api.model
#     def get_ticket_dashboard_count(self):
#         uid = request.session.uid
#         user = request.env['res.users'].browse(uid)
#         cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
#         cids = [int(cid) for cid in cids.split(',')]
#         return self.env['ir.ui.view'].with_context()._render_template('sh_all_in_one_helpdesk.ticket_dashboard_count', {
#             'data_dict': {},
#         })

#     @api.model
#     def get_ticket_counter_data(self,team_leader,team,assign_user,filter_date,start_date,end_date):
#         data_dict = {}
#         ticket_data_dic = {}
#         ticket_data_list = []
#         ticket_obj = self.env['sh.helpdesk.ticket'].search(
#             [], order='id desc', limit=1)
#         uid = request.session.uid
#         user = self.env['res.users'].browse(uid)
#         cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
#         cids = [int(cid) for cid in cids.split(',')]
#         company_id = self.env.company
#         id_list = []
#         for stage in company_id.dashboard_filter:
#             doman = []
#             id_list = []
#             if filter_date == 'today':

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     datetime.now().date().strftime("%Y/%m/%d 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'yesterday':

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 prev_day = (datetime.now().date() -
#                             relativedelta(days=1)).strftime('%Y/%m/%d 00:00:00')
#                 dt_flt1.append(prev_day)
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 prev_day = (datetime.now().date() -
#                             relativedelta(days=1)).strftime('%Y/%m/%d 23:59:59')
#                 dt_flt2.append(prev_day)
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'weekly':  # current week

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append((datetime.now().date(
#                 ) - relativedelta(weeks=1, weekday=0)).strftime("%Y/%m/%d 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'prev_week':  # Previous week

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append((datetime.now().date(
#                 ) - relativedelta(weeks=2, weekday=0)).strftime("%Y/%m/%d 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append((datetime.now().date(
#                 ) - relativedelta(weeks=1, weekday=6)).strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'monthly':  # Current Month

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     (datetime.now().date()).strftime("%Y/%m/01 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'prev_month':  # Previous Month

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     (datetime.now().date() - relativedelta(months=1)).strftime("%Y/%m/01 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/01 00:00:00"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'cur_year':  # Current Year

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     (datetime.now().date()).strftime("%Y/01/01 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'prev_year':  # Previous Year

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     (datetime.now().date() - relativedelta(years=1)).strftime("%Y/01/01 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/01/01 00:00:00"))
#                 doman.append(tuple(dt_flt2))
#             elif filter_date == 'custom':
#                 if start_date and end_date:
#                     dt_flt1 = []
#                     dt_flt1.append('create_date')
#                     dt_flt1.append('>=')
#                     dt_flt1.append(datetime.strptime(
#                         str(start_date), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
#                     doman.append(tuple(dt_flt1))

#                     dt_flt2 = []
#                     dt_flt2.append('create_date')
#                     dt_flt2.append('<=')
#                     dt_flt2.append(datetime.strptime(
#                         str(end_date), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
#                     doman.append(tuple(dt_flt2))
#             if team and team not in [None,False,""] and int(team) != 0:
#                 doman.append(('team_id', '=', int(team)))
#             elif team and team not in [None,False,""] and int(team) == 0:
#                 if self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     team_ids = self.env['sh.helpdesk.team'].search(
#                         ['|', ('team_head', '=', self.env.user.id), ('team_members', 'in', [self.env.user.id])])
#                     doman.append(('team_id', 'in', team_ids.ids))
#                 elif not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     team_ids = self.env['sh.helpdesk.team'].search(
#                         [('team_members', 'in', [self.env.user.id])])
#                     doman.append(('team_id', 'in', team_ids.ids))

#             if team_leader and team_leader not in [None,False,""] and int(team_leader) != 0:
#                 doman.append(('team_head', '=', int(team_leader)))
#             elif team_leader and team_leader not in [None,False,""] and int(team_leader) == 0:
#                 if self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     doman.append(('|'))
#                     doman.append(('|'))
#                     doman.append(('team_head', '=', self.env.user.id))
#                     doman.append(('user_id', '=', self.env.user.id))
#                     doman.append(('sh_user_ids', 'in', [self.env.user.id]))
#             if assign_user and assign_user not in [None,False,""] and int(assign_user) != 0:
#                 doman.append(('|'))
#                 doman.append(('user_id', '=', int(assign_user)))
#                 doman.append(('sh_user_ids', 'in', [int(assign_user)]))
#             elif assign_user and assign_user not in [None,False,""] and int(assign_user) == 0:
#                 if self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     doman.append(('|'))
#                     doman.append(('|'))
#                     doman.append(('sh_user_ids', 'in', [self.env.user.id]))
#                     doman.append(('user_id', '=', self.env.user.id))
#                     doman.append(('team_head', '=', self.env.user.id))
#                 elif not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     doman.append(('|'))
#                     doman.append(('user_id', '=', self.env.user.id))
#                     doman.append(('sh_user_ids', 'in', [self.env.user.id]))
#             ticket_list = []
#             doman.append(('stage_id', '=', stage.id))
#             doman.append(('company_id','in',cids))
#             search_tickets = ticket_obj.search(doman)
#             if search_tickets:
#                 for ticket in search_tickets:
#                     create_date = datetime.strftime(ticket.create_date,"%Y-%m-%d %H:%M:%S")
#                     write_date = datetime.strftime(ticket.write_date,"%Y-%m-%d %H:%M:%S")
#                     ticket_dic = {
#                         'ticket_id': ticket.id,
#                         'ticket_no': ticket.name,
#                         'partner_id': ticket.partner_id.name,
#                         'create_date': create_date,
#                         'write_date': write_date,
#                         'user_id': ticket.user_id.name,
#                     }
#                     ticket_list.append(ticket_dic)
#                     id_list.append(ticket.id)
#             search_stage = self.env['helpdesk.stages'].search([
#                 ('id', '=', stage.id)
#             ], limit=1)
#             if search_stage:
#                 ticket_data_dic.update({search_stage.name: ticket_list})
#                 list_ids = [id_list]
#                 data_dict.update({search_stage.name: list_ids})
#                 ticket_data_list.append(search_stage.name)
#         return self.env['ir.ui.view'].with_context()._render_template('sh_all_in_one_helpdesk.ticket_dashboard_count', {
#             'ticket_data_dic': ticket_data_dic,
#             'ticket_data_list': ticket_data_list,
#             'data_dict': data_dict,
#         })

#     @api.model
#     def get_ticket_table_data(self,team_leader,team,assign_user,filter_date,start_date,end_date):
#         ticket_obj = self.env['sh.helpdesk.ticket'].search(
#             [], order='id desc', limit=1)
#         uid = request.session.uid
#         user = request.env['res.users'].browse(uid)
#         cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
#         cids = [int(cid) for cid in cids.split(',')]
#         company_id = self.env.company
#         ticket_data_dic = {}
#         ticket_data_list = []
#         for stage in company_id.dashboard_tables:
#             doman = []
#             if filter_date == 'today':

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     datetime.now().date().strftime("%Y/%m/%d 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'yesterday':

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 prev_day = (datetime.now().date() -
#                             relativedelta(days=1)).strftime('%Y/%m/%d 00:00:00')
#                 dt_flt1.append(prev_day)
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 prev_day = (datetime.now().date() -
#                             relativedelta(days=1)).strftime('%Y/%m/%d 23:59:59')
#                 dt_flt2.append(prev_day)
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'weekly':  # current week

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append((datetime.now().date(
#                 ) - relativedelta(weeks=1, weekday=0)).strftime("%Y/%m/%d 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'prev_week':  # Previous week

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append((datetime.now().date(
#                 ) - relativedelta(weeks=2, weekday=0)).strftime("%Y/%m/%d 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append((datetime.now().date(
#                 ) - relativedelta(weeks=1, weekday=6)).strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'monthly':  # Current Month

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     (datetime.now().date()).strftime("%Y/%m/01 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'prev_month':  # Previous Month

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     (datetime.now().date() - relativedelta(months=1)).strftime("%Y/%m/01 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/01 00:00:00"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'cur_year':  # Current Year

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     (datetime.now().date()).strftime("%Y/01/01 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<=')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
#                 doman.append(tuple(dt_flt2))

#             elif filter_date == 'prev_year':  # Previous Year

#                 dt_flt1 = []
#                 dt_flt1.append('create_date')
#                 dt_flt1.append('>')
#                 dt_flt1.append(
#                     (datetime.now().date() - relativedelta(years=1)).strftime("%Y/01/01 00:00:00"))
#                 doman.append(tuple(dt_flt1))

#                 dt_flt2 = []
#                 dt_flt2.append('create_date')
#                 dt_flt2.append('<')
#                 dt_flt2.append(
#                     datetime.now().date().strftime("%Y/01/01 00:00:00"))
#                 doman.append(tuple(dt_flt2))
#             elif filter_date == 'custom':
#                 if start_date and end_date:
#                     dt_flt1 = []
#                     dt_flt1.append('create_date')
#                     dt_flt1.append('>=')
#                     dt_flt1.append(datetime.strptime(
#                         str(start_date), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
#                     doman.append(tuple(dt_flt1))

#                     dt_flt2 = []
#                     dt_flt2.append('create_date')
#                     dt_flt2.append('<=')
#                     dt_flt2.append(datetime.strptime(
#                         str(end_date), DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
#                     doman.append(tuple(dt_flt2))
#             if team and team not in [None,False,""] and int(team) != 0:
#                 doman.append(('team_id', '=', int(team)))
#             elif team and team not in [None,False,""] and int(team) == 0:
#                 if self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     team_ids = self.env['sh.helpdesk.team'].search(
#                         ['|', ('team_head', '=', self.env.user.id), ('team_members', 'in', [self.env.user.id])])
#                     doman.append(('team_id', 'in', team_ids.ids))
#                 elif not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     team_ids = request.env['sh.helpdesk.team'].search(
#                         [('team_members', 'in', [self.env.user.id])])
#                     doman.append(('team_id', 'in', team_ids.ids))
#             if team_leader and team_leader not in [None,False,""] and int(team_leader) != 0:
#                 doman.append(('team_head', '=', int(team_leader)))
#             elif team_leader and team_leader not in [None,False,""] and int(team_leader) == 0:
#                 if self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     doman.append(('|'))
#                     doman.append(('|'))
#                     doman.append(('team_head', '=', self.env.user.id))
#                     doman.append(('user_id', '=', self.env.user.id))
#                     doman.append(('sh_user_ids', 'in', [self.env.user.id]))
#             if assign_user and assign_user not in [None,False,""] and int(assign_user) != 0:
#                 doman.append(('|'))
#                 doman.append(('user_id', '=', int(assign_user)))
#                 doman.append(('sh_user_ids', 'in', [int(assign_user)]))
#             elif assign_user and assign_user not in [None,False,""] and int(assign_user) == 0:
#                 if self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     doman.append(('|'))
#                     doman.append(('|'))
#                     doman.append(('user_id', '=', self.env.user.id))
#                     doman.append(('sh_user_ids', 'in', [self.env.user.id]))
#                     doman.append(('team_head', '=', self.env.user.id))
#                 elif not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_team_leader') and self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_user') and not self.env.user.has_group('sh_all_in_one_helpdesk.helpdesk_group_manager'):
#                     doman.append(('|'))
#                     doman.append(('user_id', '=', self.env.user.id))
#                     doman.append(('sh_user_ids', 'in', [self.env.user.id]))
#             ticket_list = []
#             doman.append(('stage_id', '=', stage.id))
#             doman.append(('company_id','in',cids))
#             search_tickets = ticket_obj.search(doman)
#             if search_tickets:
#                 for ticket in search_tickets:
#                     create_date = datetime.strftime(ticket.create_date,"%Y-%m-%d %H:%M:%S")
#                     write_date = datetime.strftime(ticket.write_date,"%Y-%m-%d %H:%M:%S")
#                     ticket_dic = {
#                         'ticket_id': ticket.id,
#                         'ticket_no': ticket.name,
#                         'partner_name': ticket.partner_id.name_get()[0][1],
#                         'partner_mobile':ticket.partner_id.mobile,
#                         'partner_id':ticket.partner_id.id,
#                         'create_date': create_date,
#                         'write_date': write_date,
#                         'user_id': ticket.user_id.name,
#                     }
#                     ticket_list.append(ticket_dic)
#             search_stage = self.env['helpdesk.stages'].search([
#                 ('id', '=', stage.id)
#             ], limit=1)
#             if search_stage:
#                 ticket_data_dic.update({search_stage.name: ticket_list})
#                 ticket_data_list.append(search_stage.name)
#         return self.env['ir.ui.view'].with_context()._render_template('sh_all_in_one_helpdesk.ticket_dashboard_tbl', {
#             'ticket_data_dic': ticket_data_dic,
#             'ticket_data_list': ticket_data_list,
#         })

#     @api.model
#     def get_mobile_no(self,partner_id):
#         dic={}
#         if partner_id and partner_id!='select_partner':
#             partner_id = request.env['res.partner'].browse(int(partner_id))
#             if partner_id and partner_id.mobile:
#                 dic.update({
#                     'mobile':str(partner_id.mobile)
#                     })
#         return json.dumps(dic)

#     @api.model
#     def send_by_whatsapp(self, partner_id,mobile_no,message):
#         dic = {}
#         if partner_id and partner_id=='select_partner':
#             dic.update({
#                 'msg':'Partner is Required.'
#                 })
#         elif mobile_no and mobile_no=='':
#             dic.update({
#                 'msg':'Mobile Number is Required.'
#                 })
#         elif message and message=='':
#             dic.update({
#                 'msg':'Message is Required.'
#                 })
#         else:
#             dic.update({
#                 'url':str("https://web.whatsapp.com/send?l=&phone="+mobile_no+"&text=" + message)
#                 })
#         return json.dumps(dic)

#     @api.model
#     def open_tickets(self, **kw):
#         dashboard_id = self.env['ticket.dashboard'].search(
#             [('id', '=', 1)], limit=1)
#         dashboard_id.get_ticket_data(kw.get('ids'))
#         dic = {}
#         dic.update({'success': 1})
#         return json.dumps(dic)
