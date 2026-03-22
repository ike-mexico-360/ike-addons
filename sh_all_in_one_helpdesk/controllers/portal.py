# -*- coding: utf-8 -*-
# Part of Softhealer Technologies.

from odoo import fields, http, _
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.http import request
from odoo.tools import date_utils, groupby as groupbyelem
from odoo.osv.expression import AND, OR
from dateutil.relativedelta import relativedelta
from operator import itemgetter
from collections import OrderedDict
from odoo.exceptions import AccessError, MissingError
import json
import base64
import werkzeug
import logging
_logger = logging.getLogger(__name__)


class PortalHelpdesk(CustomerPortal): 
        
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'sh_ticket_count' in counters:
            ticket_domain = []
            if request.env.user.sh_portal_user_access and request.env.user.sh_portal_user_access == 'user':
                ticket_domain.append(
                    ('partner_id', '=', request.env.user.partner_id.id))
            elif request.env.user.sh_portal_user_access and request.env.user.sh_portal_user_access == 'manager':
                ticket_domain.append(('|'))
                ticket_domain.append(('create_uid', '=', request.env.user.id))
                ticket_domain.append(
                    ('partner_id', '=', request.env.user.partner_id.id))
            else:
                ticket_domain.append(
                    ('partner_id', '=', request.env.user.partner_id.id))
            ticket_count = request.env['sh.helpdesk.ticket'].sudo(
            ).search_count(ticket_domain)
            if ticket_count==0:
                values['sh_ticket_count'] = '0'
            else:
                values['sh_ticket_count'] = ticket_count
        return values


    def _prepare_portal_layout_values(self):
        values = super(PortalHelpdesk, self)._prepare_portal_layout_values()
        return values

    @http.route(['/my/sh_tickets', '/my/sh_tickets/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_tickets(self, page=1, sortby=None, filterby=None, search=None, search_in='all', groupby='create_by', **kw):
        print("\n\n\n\n\n\n50 self",self)
        values = self._prepare_portal_layout_values()

        HelpdeskTicket = request.env['sh.helpdesk.ticket'].sudo()

        searchbar_sortings = {
            'create_date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
        }
        searchbar_inputs = {
            'all': {'input': 'all', 'label': _('Search in All')},
            'name': {'input': 'name', 'label': _('Search in Name')},
            'description': {'input': 'description', 'label': _('Search in Description')},
            'category': {'input': 'category', 'label': _('Search in Category')},
            'email_subject': {'input': 'email_subject', 'label': _('Search in Email Subject')},
        }

        searchbar_groupby = {
            'create_by': {'input': 'create_by', 'label': _('Created By')},
            'ticket_type': {'input': 'ticket_type', 'label': _('Ticket Type')},
            'status': {'input': 'status', 'label': _('Status')},
            'customer': {'input': 'customer', 'label': _('Customer')},
            'category': {'input': 'category', 'label': _('Category')},
            'subcategory': {'input': 'subcategory', 'label': _('Sub Category')},
            'subject': {'input': 'subject', 'label': _('Subject')},
            'priority': {'input': 'priority', 'label': _('Priority')},
            'state': {'input': 'state', 'label': _('Reply Status')},
        }

        today = fields.Date.today()
        quarter_start, quarter_end = date_utils.get_quarter(today)
        last_week = today + relativedelta(weeks=-1)
        last_month = today + relativedelta(months=-1)
        last_year = today + relativedelta(years=-1)

        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'today': {'label': _('Today'), 'domain': [("create_date", "=", today)]},
            'week': {'label': _('This week'), 'domain': [('create_date', '>=', date_utils.start_of(today, "week")), ('create_date', '<=', date_utils.end_of(today, 'week'))]},
            'month': {'label': _('This month'), 'domain': [('create_date', '>=', date_utils.start_of(today, 'month')), ('create_date', '<=', date_utils.end_of(today, 'month'))]},
            'year': {'label': _('This year'), 'domain': [('create_date', '>=', date_utils.start_of(today, 'year')), ('create_date', '<=', date_utils.end_of(today, 'year'))]},
            'quarter': {'label': _('This Quarter'), 'domain': [('create_date', '>=', quarter_start), ('create_date', '<=', quarter_end)]},
            'last_week': {'label': _('Last week'), 'domain': [('create_date', '>=', date_utils.start_of(last_week, "week")), ('create_date', '<=', date_utils.end_of(last_week, 'week'))]},
            'last_month': {'label': _('Last month'), 'domain': [('create_date', '>=', date_utils.start_of(last_month, 'month')), ('create_date', '<=', date_utils.end_of(last_month, 'month'))]},
            'last_year': {'label': _('Last year'), 'domain': [('create_date', '>=', date_utils.start_of(last_year, 'year')), ('create_date', '<=', date_utils.end_of(last_year, 'year'))]},
        }
        # default sort by value
        if not sortby:
            sortby = 'create_date'
        order = searchbar_sortings[sortby]['order']
        # default filter by value
        if not filterby:
            filterby = 'all'
        domain = AND([searchbar_filters[filterby]['domain']])

        if search and search_in:
            search_sub_domains = []
            if search_in in ('all', 'name'):
                search_sub_domains.append([('name', 'ilike', search)])
            if search_in in ('all', 'description'):
                search_sub_domains.append([('description', 'ilike', search)])
            if search_in in ('all', 'category'):
                search_sub_domains.append([('category_id', 'ilike', search)])
            if search_in in ('all', 'email_subject'):
                search_sub_domains.append([('email_subject', 'ilike', search)])
            domain = AND([domain, OR(search_sub_domains)])
        ticket_domain = []
        if request.env.user.sh_portal_user_access and request.env.user.sh_portal_user_access == 'user':
            ticket_domain.append(('partner_id', '=', request.env.user.partner_id.id))
        elif request.env.user.sh_portal_user_access and request.env.user.sh_portal_user_access == 'manager':
            ticket_domain.append(('|'))
            ticket_domain.append(('create_uid', '=', request.env.user.id))
            ticket_domain.append(('partner_id', '=', request.env.user.partner_id.id))
        else:
            ticket_domain.append(('partner_id', '=', request.env.user.partner_id.id))
        domain = AND([domain, ticket_domain])

        # count for pager
        sh_ticket_count = HelpdeskTicket.search_count(domain)
        # pager
        pager = portal_pager(
            url="/my/sh_tickets",
            url_args={'sortby': sortby, 'search_in': search_in,
                      'search': search, 'filterby': filterby},
            total=sh_ticket_count,
            page=page,
            step=self._items_per_page
        )
        if groupby == 'create_by':
            order = "create_uid, %s" % order
        elif groupby == 'ticket_type':
            order = "ticket_type, %s" % order
        elif groupby == 'status':
            order = "stage_id, %s" % order
        elif groupby == 'customer':
            order = "partner_id, %s" % order
        elif groupby == 'category':
            order = "category_id, %s" % order
        elif groupby == 'subcategory':
            order = "sub_category_id, %s" % order
        elif groupby == 'subject':
            order = "subject_id, %s" % order
        elif groupby == 'priority':
            order = "priority, %s" % order
        elif groupby == 'state':
            order = 'state,%s' % order
        tickets = HelpdeskTicket.search(
            domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_tickets_history'] = tickets.ids[:100]
        if groupby == 'create_by':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('create_uid'))]
        elif groupby == 'ticket_type':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('ticket_type'))]
        elif groupby == 'status':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('stage_id'))]
        elif groupby == 'customer':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('partner_id'))]
        elif groupby == 'category':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('category_id'))]
        elif groupby == 'subcategory':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('sub_category_id'))]
        elif groupby == 'subject':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('subject_id'))]
        elif groupby == 'priority':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('priority'))]
        elif groupby == 'state':
            grouped_tickets = [HelpdeskTicket.concat(
                *g) for k, g in groupbyelem(tickets, itemgetter('state'))]
        # content according to pager and archive selected
        print("\n\n\n\n\n\n173 tickets",tickets)
        values.update({
            'sh_tickets': tickets,
            'grouped_tickets': grouped_tickets,
            'page_name': 'sh_ticket',
            'default_url': '/my/sh_tickets',
            'sh_ticket_count': sh_ticket_count,
            'pager': pager,
            'searchbar_sortings': searchbar_sortings,
            'search_in': search_in,
            'sortby': sortby,
            'groupby': groupby,
            'searchbar_inputs': searchbar_inputs,
            'searchbar_groupby': searchbar_groupby,
            'searchbar_filters': OrderedDict(sorted(searchbar_filters.items())),
            'filterby': filterby,
        })

        return request.render("sh_all_in_one_helpdesk.portal_my_tickets", values)

    @http.route(['/my/sh_tickets/<int:ticket_id>'], type='http', auth="public", website=True)
    def portal_my_ticket_detail(self, ticket_id, access_token=None, report_type=None, message=False, download=False, **kw):
        try:
            ticket_sudo = self._document_check_access(
                'sh.helpdesk.ticket', ticket_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        if report_type in ('html', 'pdf', 'text'):
            return self._show_report(model=ticket_sudo, report_type=report_type, report_ref='sh_all_in_one_helpdesk.report_helpdeskticket', download=download)
        if ticket_sudo:
            if request.env.company.sh_receive_email_seeing_ticket:
                body = _('Ticket viewed by customer %s',
                         ticket_sudo.partner_id.name)
                ticket_sudo.message_post(
                    body=body,
                    # token=ticket_sudo.access_token,
                    message_type="notification",
                    subtype_xmlid="mail.mt_note",
                    partner_ids=ticket_sudo.user_id.sudo().partner_id.ids,
                )
        values = {
            'token': access_token,
            'sh_ticket': ticket_sudo,
            'message': message,
            'bootstrap_formatting': True,
            'partner_id': ticket_sudo.partner_id.id,
            'report_type': 'html',
        }

        return request.render("sh_all_in_one_helpdesk.portal_ticket_page", values)

    @http.route('/portal-subcategory-data', type="http",auth="user", csrf=False)
    def portal_sub_category_data(self, **kw):
        dic = {}
        if kw.get('category_id') and kw.get('category_id') != 'category':
            sub_categ_list = []
            sub_categ_ids = request.env['helpdesk.subcategory'].sudo().search(
                [('parent_category_id', '=', int(kw.get('category_id')))])
            for sub in sub_categ_ids:
                sub_categ_dic = {
                    'id': sub.id,
                    'name': sub.name,
                }
                sub_categ_list.append(sub_categ_dic)
            dic.update({
                'sub_categories': sub_categ_list
            })
        else:
            dic.update({
                'sub_categories': []
            })
        return json.dumps(dic)

    @http.route('/portal-partner-data', type="http", auth="user", csrf=False)
    def portal_partner_data(self, **kw):
        dic = {}
        partner_list = []
        for partner in request.env['res.partner'].sudo().search([]):
            partner_dic = {
                'id': partner.id,
                'name': partner.name,
            }
            partner_list.append(partner_dic)
        dic.update({
            'partners': partner_list
        })
        return json.dumps(dic)


    @http.route('/selected-partner-data', type="http", auth="user", csrf=False)
    def selected_partner_data(self, **kw):
        dic = {}
        if kw.get('partner_id') and kw.get('partner_id') != '':
            partner = request.env['res.partner'].sudo().search(
                [('id', '=', int(kw.get('partner_id')))], limit=1)
            if partner:
                dic.update({
                    'name': partner.name,
                    'email': partner.email,
                })
        return json.dumps(dic)

    @http.route('/portal-create-ticket', type='http', auth="user", csrf=False)
    def portal_create_ticket(self, **kw):
        try:
            ticket_dic = {}
            partner_id = False
            if kw.get('partner_id') and kw.get('partner_id') != '':
                partner_id = request.env['res.partner'].sudo().search(
                    [('id', '=', int(kw.get('partner_id')))], limit=1)
            else:
                partner_id = request.env['res.partner'].sudo().search(
                    [('email', '=', kw.get('portal_email'))], limit=1)
            if not partner_id:
                partner_id = request.env['res.partner'].sudo().create({
                    'name':kw.get('portal_contact_name'),
                    'company_type': 'person',
                    'email':kw.get('portal_email'),
                    'company_id':request.env.company.id
                })
            if kw.get('portal_email'):
                if partner_id:
                    ticket_dic.update({
                        'partner_id':partner_id.id,
                        'company_id':request.env.company.id
                    })

                    if kw.get('portal_email_subject'):
                        ticket_dic.update({
                            'email_subject':kw.get('portal_email_subject')
                        })
                    if kw.get('portal_email'):
                        ticket_dic.update({
                            'email':kw.get('portal_email')
                        })
                    if kw.get('portal_contact_name'):
                        ticket_dic.update({
                            'person_name':kw.get('portal_contact_name'),
                        })
                    if kw.get('portal_type') and kw.get('portal_type')!='type':
                        ticket_dic.update({
                            'ticket_type':int(kw.get('portal_type')),
                        })
                    if kw.get('portal_priority'):
                        if kw.get('portal_priority')!='priority':
                            portal_priority=int(kw.get('portal_priority')) or False
                            ticket_dic.update({
                                'priority':portal_priority,
                            })
                    if kw.get('portal_category') and kw.get('portal_category')!='category':
                        ticket_dic.update({
                            'category_id':int(kw.get('portal_category')),
                        })
                    if kw.get('portal_subcategory') and kw.get('portal_subcategory')!='sub_category':
                        ticket_dic.update({
                            'sub_category_id':int(kw.get('portal_subcategory')),
                        })
                    if kw.get('portal_description'):
                        ticket_dic.update({
                            'description':kw.get('portal_description'),
                        })
                    # team_id=False
                    # if request.env.company and request.env.company.sh_default_team_id:
                    #     team_id = request.env['sh.helpdesk.team'].sudo().search([('id','=',request.env.company.sh_default_team_id.id)], limit=1).id
                    # ticket_dic.update({
                    #     'team_id':team_id,
                    #     'name':kw.get('portal_email_subject') if kw.get('portal_email_subject') else '',
                    # })

                    # if(kw.get("portal_file")):
                    #     print("Yes")
                    # else:
                    #     print("No")





                    ticket_id = request.env['sh.helpdesk.ticket'].sudo().create(ticket_dic)
                    if ticket_id:
                        if kw.get('portal_file'):
                            attached_files = request.httprequest.files.getlist(
                                'portal_file')

                            print(f'attached_files ===========> {attached_files}')
                            

                            attachment_ids = []
                            for attachment in attached_files:
                                result = base64.b64encode(attachment.read())
                                attachment_id = request.env['ir.attachment'].sudo().create({
                                    'name': attachment.filename,
                                    'res_model': 'sh.helpdesk.ticket',
                                    'res_id': ticket_id.id,
                                    'display_name': attachment.filename,
                                    'datas': result,
                                })
                                print(f'attachment_id ===========> {attachment_id} ')
                                
                                attachment_ids.append(attachment_id.id)
            return werkzeug.utils.redirect("/my/sh_tickets")
        except Exception as e:
            _logger.exception('Something went wrong %s',str(e))
            

