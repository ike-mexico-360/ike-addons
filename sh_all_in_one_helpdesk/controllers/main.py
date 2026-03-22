# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import http, _
from odoo.http import request, content_disposition
import json
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import re
from odoo.exceptions import AccessError, MissingError, UserError


class DownloadReport(http.Controller):
    def _document_check_access(self,
                               model_name,
                               document_id,
                               access_token=None):
        document = request.env[model_name].browse([document_id])
        document_sudo = document.sudo().exists()
        if not document_sudo:
            raise MissingError(_("This document does not exist."))
        if access_token and document_sudo.report_token and access_token == document_sudo.report_token:
            return document_sudo
        else:
            raise AccessError(
                _("Sorry, you are not allowed to access this document."))

    def _show_report(self, model, report_type, report_ref, download=False):
        if report_type not in ('html', 'pdf', 'text'):
            raise UserError(_("Invalid report type: %s", report_type))

        report_sudo = request.env.ref(report_ref).sudo()

        if not isinstance(report_sudo, type(request.env['ir.actions.report'])):
            raise UserError(
                _("%s is not the reference of a report", report_ref))

        method_name = '_render_qweb_%s' % (report_type)
        report = getattr(report_sudo, method_name)(report_ref, [model.id],
                                                   data={
                                                       'report_type':
                                                       report_type
        })[0]
        reporthttpheaders = [
            ('Content-Type',
             'application/pdf' if report_type == 'pdf' else 'text/html'),
            ('Content-Length', len(report)),
        ]
        if report_type == 'pdf' and download:
            filename = "%s.pdf" % (re.sub(r'\W+', '-',
                                          model._get_report_base_filename()))
            reporthttpheaders.append(
                ('Content-Disposition', content_disposition(filename)))
            return request.make_response(report, headers=reporthttpheaders)

    # @http.route(['/download/ht/<int:ticket_id>'],
    #             type='http',
    #             auth="public",
    #             website=True)
    # def download_ticket(self,
    #                     ticket_id,
    #                     report_type=None,
    #                     access_token=None,
    #                     message=False,
    #                     download=False,
    #                     **kw):
    #     try:
    #         ticket_sudo = self._document_check_access(
    #             'sh.helpdesk.ticket', ticket_id, access_token=access_token)
    #     except (AccessError, MissingError):
    #         return '<br/><br/><center><h1><b>Oops Invalid URL! Please check URL and try again!</b></h1></center>'
    #     report_type = 'pdf'
    #     download = True
    #     return self._show_report(
    #         model=ticket_sudo,
    #         report_type=report_type,
    #         report_ref='sh_all_in_one_helpdesk.action_report_sh_helpdesk_ticket',
    #         download=download)

    @http.route(['/download/ht/<int:ticket_id>'], type='http',auth="public",
                website=True)
    def download_ticket(self,
                        ticket_id,
                        report_type=None,
                        access_token=None,
                        message=False,
                        download=False,
                        **kw):
        try:
            ticket_sudo = self._document_check_access('sh.helpdesk.ticket', ticket_id, access_token=access_token)
        except (AccessError, MissingError):
            return '<br/><br/><center><h1><b>Oops Invalid URL! Please check URL and try again!</b></h1></center>'
        report_type = 'pdf'
        download = True
        return self._show_report(
            model=ticket_sudo,
            report_type=report_type,
            report_ref='sh_all_in_one_helpdesk.action_report_sh_helpdesk_ticket',
            download=download)


class HelpdeskTicketFeedbackController(http.Controller):
    @http.route('/ticket/feedback/<ticket_id>',
                type="http",
                auth="public",
                website=True)
    def helpdesk_ticket_feedback(self, ticket_id, **kw):
        return http.request.render(
            'sh_all_in_one_helpdesk.sh_helpdesk_ticket_feedback_page',
            {'ticket': ticket_id})

    @http.route('/helpdesk/ticket/feedback',
                type="http",
                auth="public",
                website=True,
                csrf=False)
    def helpdesk_ticket_feedback_thanks(self, ticket_id, **kw):
        dic = {}
        if kw.get('smiley') != '':
            dic.update({
                'priority_new': kw.get('smiley'),
            })
        if kw.get('comment') != '':
            dic.update({
                'customer_comment': kw.get('comment'),
            })
        ticket = request.env['sh.helpdesk.ticket'].sudo().search(
            [('id', '=', int(ticket_id))], limit=1)
        if ticket:
            ticket.sudo().write(dic)
        return http.request.render(
            'sh_all_in_one_helpdesk.ticket_feedback_thank_you', {})

    # @http.route('/get_team', type='http', auth="public")
    # def team_data(self):

    #     team_obj = request.env['sh.helpdesk.team'].sudo().search([])
    #     res_list = {}

    #     for rec in team_obj:
    #         res = {}
    #         res.update({'name': rec.name})
    #         res_list.update({rec.id: res})
    #     return json.dumps(res_list)

    # @http.route('/get_team_leader', type='http', auth="public")
    # def get_team_leader_data(self):
    #     team_heads = request.env['sh.helpdesk.team'].sudo().search(
    #         []).mapped('team_head')
    #     res_list = {}
    #     if team_heads:
    #         for rec in team_heads:
    #             res = {}
    #             res.update({'name': rec.name})
    #             res_list.update({rec.id: res})
    #     return json.dumps(res_list)

    # @http.route([
    #     '/get-leader-user',
    # ],
    #     type='http',
    #     auth="public",
    #     methods=["POST"],
    #     website=True,
    #     csrf=False)
    # def get_data(self, **post):
    #     dic = {}
    #     if int(post.get('team_leader')) != 0:
    #         team_ids = request.env['sh.helpdesk.team'].sudo().search([
    #             ('team_head', '=', int(post.get('team_leader')))
    #         ])
    #         for rec in team_ids:
    #             res = {}
    #             res.update({'name': rec.name})
    #             dic.update({rec.id: res})
    #     return json.dumps(dic)

    # @http.route([
    #     '/user-group',
    # ],
    #     type='http',
    #     auth="public",
    #     methods=["POST"],
    #     website=True,
    #     csrf=False)
    # def get_user_group(self, **post):
    #     dic = {}
    #     support_user = request.env.user.has_group(
    #         'sh_all_in_one_helpdesk.helpdesk_group_user')
    #     team_leader = request.env.user.has_group(
    #         'sh_all_in_one_helpdesk.helpdesk_group_team_leader')
    #     manager = request.env.user.has_group(
    #         'sh_all_in_one_helpdesk.helpdesk_group_manager')
    #     if support_user and not team_leader and not manager:
    #         dic.update({'user': '1'})
    #     elif support_user and team_leader and not manager:
    #         dic.update({'leader': '1'})
    #     elif support_user and team_leader and manager:
    #         dic.update({'manager': '1'})
    #     return json.dumps(dic)

    # @http.route([
    #     '/get-user',
    # ],
    #     type='http',
    #     auth="public",
    #     methods=["POST"],
    #     website=True,
    #     csrf=False)
    # def get_user(self, **post):
    #     dic = {}
    #     if int(post.get('team')) != 0:
    #         team_id = request.env['sh.helpdesk.team'].sudo().search([
    #             ('id', '=', int(post.get('team')))
    #         ])
    #         for rec in team_id.team_members:
    #             res = {}
    #             res.update({'name': rec.name})
    #             dic.update({rec.id: res})
    #     return json.dumps(dic)

    # @http.route('/get-ticket-counter-data', type='http', auth="public")
    # def get_ticket_counter_data(self, **kw):
    #     ticket_obj = request.env['sh.helpdesk.ticket'].sudo().search(
    #         [], order='id desc', limit=1)
    #     uid = request.session.uid
    #     user = request.env['res.users'].sudo().browse(uid)
    #     cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
    #     cids = [int(cid) for cid in cids.split(',')]
    #     company_id = request.env.company
    #     ticket_data_dic = {}
    #     ticket_data_list = []
    #     id_list = []
    #     data_dict = {}
    #     for stage in company_id.dashboard_filter:
    #         doman = []
    #         id_list = []
    #         if kw.get('filter_date') == 'today':

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'yesterday':

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             prev_day = (
    #                 datetime.now().date() -
    #                 relativedelta(days=1)).strftime('%Y/%m/%d 00:00:00')
    #             dt_flt1.append(prev_day)
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             prev_day = (
    #                 datetime.now().date() -
    #                 relativedelta(days=1)).strftime('%Y/%m/%d 23:59:59')
    #             dt_flt2.append(prev_day)
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'weekly':  # current week

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append((datetime.now().date() - relativedelta(
    #                 weeks=1, weekday=0)).strftime("%Y/%m/%d 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'prev_week':  # Previous week

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append((datetime.now().date() - relativedelta(
    #                 weeks=2, weekday=0)).strftime("%Y/%m/%d 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append((datetime.now().date() - relativedelta(
    #                 weeks=1, weekday=6)).strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'monthly':  # Current Month

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 (datetime.now().date()).strftime("%Y/%m/01 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'prev_month':  # Previous Month

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 (datetime.now().date() -
    #                  relativedelta(months=1)).strftime("%Y/%m/01 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/01 00:00:00"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'cur_year':  # Current Year

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 (datetime.now().date()).strftime("%Y/01/01 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'prev_year':  # Previous Year

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 (datetime.now().date() -
    #                  relativedelta(years=1)).strftime("%Y/01/01 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/01/01 00:00:00"))
    #             doman.append(tuple(dt_flt2))
    #         elif kw.get('filter_date') == 'custom':
    #             if kw.get('date_start') and kw.get('date_end'):
    #                 dt_flt1 = []
    #                 dt_flt1.append('create_date')
    #                 dt_flt1.append('>=')
    #                 dt_flt1.append(
    #                     datetime.strptime(
    #                         str(kw.get('date_start')),
    #                         DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
    #                 doman.append(tuple(dt_flt1))

    #                 dt_flt2 = []
    #                 dt_flt2.append('create_date')
    #                 dt_flt2.append('<=')
    #                 dt_flt2.append(
    #                     datetime.strptime(
    #                         str(kw.get('date_end')),
    #                         DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
    #                 doman.append(tuple(dt_flt2))
    #         if int(kw.get('team')) != 0:
    #             doman.append(('team_id', '=', int(kw.get('team'))))
    #         elif int(kw.get('team')) == 0:
    #             if request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 team_ids = request.env['sh.helpdesk.team'].sudo().search([
    #                     '|', ('team_head', '=', request.env.user.id),
    #                     ('team_members', 'in', [request.env.user.id])
    #                 ])
    #                 doman.append(('team_id', 'in', team_ids.ids))
    #             elif not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 team_ids = request.env['sh.helpdesk.team'].sudo().search([
    #                     ('team_members', 'in', [request.env.user.id])
    #                 ])
    #                 doman.append(('team_id', 'in', team_ids.ids))

    #         if int(kw.get('team_leader')) != 0:
    #             doman.append(('team_head', '=', int(kw.get('team_leader'))))
    #         elif int(kw.get('team_leader')) == 0:
    #             if request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 doman.append(('|'))
    #                 doman.append(('|'))
    #                 doman.append(('team_head', '=', request.env.user.id))
    #                 doman.append(('user_id', '=', request.env.user.id))
    #                 doman.append(('sh_user_ids', 'in', [request.env.user.id]))
    #         if int(kw.get('user_id')) != 0:
    #             doman.append(('|'))
    #             doman.append(('user_id', '=', int(kw.get('user_id'))))
    #             doman.append(('sh_user_ids', 'in', [int(kw.get('user_id'))]))
    #         elif int(kw.get('user_id')) == 0:
    #             if request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 doman.append(('|'))
    #                 doman.append(('|'))
    #                 doman.append(('sh_user_ids', 'in', [request.env.user.id]))
    #                 doman.append(('user_id', '=', request.env.user.id))
    #                 doman.append(('team_head', '=', request.env.user.id))
    #             elif not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 doman.append(('|'))
    #                 doman.append(('user_id', '=', request.env.user.id))
    #                 doman.append(('sh_user_ids', 'in', [request.env.user.id]))
    #         ticket_list = []
    #         doman.append(('stage_id', '=', stage.id))
    #         doman.append(('company_id', 'in', cids))
    #         search_tickets = ticket_obj.sudo().search(doman)
    #         if search_tickets:
    #             for ticket in search_tickets:
    #                 create_date = datetime.strftime(ticket.create_date,
    #                                                 "%Y-%m-%d %H:%M:%S")
    #                 write_date = datetime.strftime(ticket.write_date,
    #                                                "%Y-%m-%d %H:%M:%S")
    #                 ticket_dic = {
    #                     'ticket_id': ticket.id,
    #                     'ticket_no': ticket.name,
    #                     'partner_id': ticket.partner_id.name,
    #                     'create_date': create_date,
    #                     'write_date': write_date,
    #                     'user_id': ticket.user_id.name,
    #                 }
    #                 ticket_list.append(ticket_dic)
    #                 id_list.append(ticket.id)
    #         search_stage = request.env['helpdesk.stages'].sudo().search(
    #             [('id', '=', stage.id)], limit=1)
    #         if search_stage:
    #             ticket_data_dic.update({search_stage.name: ticket_list})
    #             list_ids = [id_list]
    #             data_dict.update({search_stage.name: list_ids})
    #             ticket_data_list.append(search_stage.name)
    #     return request.env['ir.ui.view'].with_context()._render_template(
    #         'sh_all_in_one_helpdesk.ticket_dashboard_count', {
    #             'ticket_data_dic': ticket_data_dic,
    #             'ticket_data_list': ticket_data_list,
    #             'data_dict': data_dict,
    #         })

    @http.route([
        '/open-ticket',
    ],
        type='http',
        auth="public",
        methods=["POST"],
        website=True,
        csrf=False)
    def open_tickets(self, **kw):
        dashboard_id = request.env['ticket.dashboard'].sudo().search(
            [('id', '=', 1)], limit=1)
        dashboard_id.get_ticket_data(kw.get('ids'))
        dic = {}
        dic.update({'success': 1})
        return json.dumps(dic)

    # @http.route('/get-ticket-table-data', type='http', auth="public")
    # def get_ticket_table_data(self, **kw):
    #     ticket_obj = request.env['sh.helpdesk.ticket'].sudo().search(
    #         [], order='id desc', limit=1)
    #     company_id = request.env.company
    #     uid = request.session.uid
    #     user = request.env['res.users'].sudo().browse(uid)
    #     cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
    #     cids = [int(cid) for cid in cids.split(',')]
    #     ticket_data_dic = {}
    #     ticket_data_list = []
    #     for stage in company_id.dashboard_tables:
    #         doman = []
    #         if kw.get('filter_date') == 'today':

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'yesterday':

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             prev_day = (
    #                 datetime.now().date() -
    #                 relativedelta(days=1)).strftime('%Y/%m/%d 00:00:00')
    #             dt_flt1.append(prev_day)
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             prev_day = (
    #                 datetime.now().date() -
    #                 relativedelta(days=1)).strftime('%Y/%m/%d 23:59:59')
    #             dt_flt2.append(prev_day)
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'weekly':  # current week

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append((datetime.now().date() - relativedelta(
    #                 weeks=1, weekday=0)).strftime("%Y/%m/%d 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'prev_week':  # Previous week

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append((datetime.now().date() - relativedelta(
    #                 weeks=2, weekday=0)).strftime("%Y/%m/%d 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append((datetime.now().date() - relativedelta(
    #                 weeks=1, weekday=6)).strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'monthly':  # Current Month

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 (datetime.now().date()).strftime("%Y/%m/01 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'prev_month':  # Previous Month

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 (datetime.now().date() -
    #                  relativedelta(months=1)).strftime("%Y/%m/01 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/01 00:00:00"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'cur_year':  # Current Year

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 (datetime.now().date()).strftime("%Y/01/01 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<=')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/%m/%d 23:59:59"))
    #             doman.append(tuple(dt_flt2))

    #         elif kw.get('filter_date') == 'prev_year':  # Previous Year

    #             dt_flt1 = []
    #             dt_flt1.append('create_date')
    #             dt_flt1.append('>')
    #             dt_flt1.append(
    #                 (datetime.now().date() -
    #                  relativedelta(years=1)).strftime("%Y/01/01 00:00:00"))
    #             doman.append(tuple(dt_flt1))

    #             dt_flt2 = []
    #             dt_flt2.append('create_date')
    #             dt_flt2.append('<')
    #             dt_flt2.append(
    #                 datetime.now().date().strftime("%Y/01/01 00:00:00"))
    #             doman.append(tuple(dt_flt2))
    #         elif kw.get('filter_date') == 'custom':
    #             if kw.get('date_start') and kw.get('date_end'):
    #                 dt_flt1 = []
    #                 dt_flt1.append('create_date')
    #                 dt_flt1.append('>=')
    #                 dt_flt1.append(
    #                     datetime.strptime(
    #                         str(kw.get('date_start')),
    #                         DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
    #                 doman.append(tuple(dt_flt1))

    #                 dt_flt2 = []
    #                 dt_flt2.append('create_date')
    #                 dt_flt2.append('<=')
    #                 dt_flt2.append(
    #                     datetime.strptime(
    #                         str(kw.get('date_end')),
    #                         DEFAULT_SERVER_DATE_FORMAT).strftime("%Y/%m/%d"))
    #                 doman.append(tuple(dt_flt2))
    #         if int(kw.get('team')) != 0:
    #             doman.append(('team_id', '=', int(kw.get('team'))))
    #         elif int(kw.get('team')) == 0:
    #             if request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 team_ids = request.env['sh.helpdesk.team'].sudo().search([
    #                     '|', ('team_head', '=', request.env.user.id),
    #                     ('team_members', 'in', [request.env.user.id])
    #                 ])
    #                 doman.append(('team_id', 'in', team_ids.ids))
    #             elif not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 team_ids = request.env['sh.helpdesk.team'].sudo().search([
    #                     ('team_members', 'in', [request.env.user.id])
    #                 ])
    #                 doman.append(('team_id', 'in', team_ids.ids))
    #         if int(kw.get('team_leader')) != 0:
    #             doman.append(('team_head', '=', int(kw.get('team_leader'))))
    #         elif int(kw.get('team_leader')) == 0:
    #             if request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 doman.append(('|'))
    #                 doman.append(('|'))
    #                 doman.append(('team_head', '=', request.env.user.id))
    #                 doman.append(('user_id', '=', request.env.user.id))
    #                 doman.append(('sh_user_ids', 'in', [request.env.user.id]))
    #         if int(kw.get('user_id')) != 0:
    #             doman.append(('|'))
    #             doman.append(('user_id', '=', int(kw.get('user_id'))))
    #             doman.append(('sh_user_ids', 'in', [int(kw.get('user_id'))]))
    #         elif int(kw.get('user_id')) == 0:
    #             if request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 doman.append(('|'))
    #                 doman.append(('|'))
    #                 doman.append(('user_id', '=', request.env.user.id))
    #                 doman.append(('sh_user_ids', 'in', [request.env.user.id]))
    #                 doman.append(('team_head', '=', request.env.user.id))
    #             elif not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_team_leader'
    #             ) and request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_user'
    #             ) and not request.env.user.has_group(
    #                     'sh_all_in_one_helpdesk.helpdesk_group_manager'):
    #                 doman.append(('|'))
    #                 doman.append(('user_id', '=', request.env.user.id))
    #                 doman.append(('sh_user_ids', 'in', [request.env.user.id]))
    #         ticket_list = []
    #         doman.append(('stage_id', '=', stage.id))
    #         doman.append(('company_id', 'in', cids))
    #         search_tickets = ticket_obj.sudo().search(doman)
    #         if search_tickets:
    #             for ticket in search_tickets:
    #                 create_date = datetime.strftime(ticket.create_date,
    #                                                 "%Y-%m-%d %H:%M:%S")
    #                 write_date = datetime.strftime(ticket.write_date,
    #                                                "%Y-%m-%d %H:%M:%S")
    #                 ticket_dic = {
    #                     'ticket_id': ticket.id,
    #                     'ticket_no': ticket.name,
    #                     'partner_name': ticket.partner_id.name_get()[0][1],
    #                     'partner_mobile': ticket.partner_id.mobile,
    #                     'partner_id': ticket.partner_id.id,
    #                     'create_date': create_date,
    #                     'write_date': write_date,
    #                     'user_id': ticket.user_id.name,
    #                 }
    #                 ticket_list.append(ticket_dic)
    #         search_stage = request.env['helpdesk.stages'].sudo().search(
    #             [('id', '=', stage.id)], limit=1)
    #         if search_stage:
    #             ticket_data_dic.update({search_stage.name: ticket_list})
    #             ticket_data_list.append(search_stage.name)
    #     return request.env['ir.ui.view'].with_context()._render_template(
    #         'sh_all_in_one_helpdesk.ticket_dashboard_tbl', {
    #             'ticket_data_dic': ticket_data_dic,
    #             'ticket_data_list': ticket_data_list,
    #         })

    # @http.route('/get-mobile-no', type='http', auth="public", csrf=False)
    # def get_mobile_no(self, **kw):
    #     dic = {}
    #     if kw.get('partner_id') and kw.get('partner_id') != 'select_partner':
    #         partner_id = request.env['res.partner'].sudo().browse(
    #             int(kw.get('partner_id')))
    #         if partner_id and partner_id.mobile:
    #             dic.update({'mobile': str(partner_id.mobile)})
    #     return json.dumps(dic)

    # @http.route('/send-by-whatsapp', type='http', auth="public", csrf=False)
    # def send_by_whatsapp(self, **kw):
    #     dic = {}
    #     if kw.get('partner_id') == 'select_partner':
    #         dic.update({'msg': 'Partner is Required.'})
    #     elif kw.get('partner_mobile_no') == '':
    #         dic.update({'msg': 'Mobile Number is Required.'})
    #     elif kw.get('message') == '':
    #         dic.update({'msg': 'Message is Required.'})
    #     else:
    #         dic.update({
    #             'url':
    #             str("https://web.whatsapp.com/send?l=&phone=" +
    #                 kw.get('partner_mobile_no') + "&text=" + kw.get('message'))
    #         })
    #     return json.dumps(dic)
