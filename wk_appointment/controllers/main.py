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

from datetime import datetime, timedelta
from odoo import http
import logging
from odoo.http import request
_logger = logging.getLogger(__name__)


class AppointmentDashboard(http.Controller):

    @http.route('/get/appointment/earning/dashboard-data', type='json', auth='user')
    def get_appointment_earning_dashboard_data(self, **post):
        """
        Get Appointment Data for the dashboard, showing data for all statuses (new, pending, completed, cancelled, approved).
        """
        appointee_id = post.get('appointee_id', '')
        selected_interval = post.get('selected_interval', 'Weekly')
        year = datetime.today().year
        current_date = datetime.today()
        year_labels = []
        appointment_obj = request.env['appointment']
        is_manager_group = request.env.user.has_group('wk_appointment.appointment_manager_group')
        is_officer_group = request.env.user.has_group('wk_appointment.appointment_officer_group')
        is_appointee_group = request.env.user.has_group('wk_appointment.appointment_appointee_group')

        # checking if the logged in user is appointee, officer or manager
        if is_appointee_group and not is_manager_group and not is_officer_group:
            appointee_id = request.env.user.partner_id.id
            post['appointee_id'] = request.env.user.partner_id.id

        # Get appointment data for all appointees
        appointment_data = appointment_obj.get_appointee_list(post)
        week_labels = ["Monday", "Tuesday", "Wedneday", "Thursday", "Friday", "Saturday", "Sunday"]
        month_labels = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

        for i in range(10,-1,-1):
            year_labels.append(str(year - i))  # Display last 10 years

        earnings_data = {
            "earnings": appointment_obj.get_earnings_by_interval(selected_interval, current_date, appointee_id),
        }

        res = {
            "appointee_list": appointment_data.get('appointee_list'),
            "earnings_data": earnings_data,  # Earnings data
            "week_labels": week_labels,
            "month_labels": month_labels,
            "year_labels": year_labels,
            "is_manager_group": is_manager_group,
            "is_officer_group": is_officer_group,
        }
        return res

    @http.route('/get/appointment/status/dashboard-data', type='json', auth='user')
    def get_appointment_status_dashboard_data(self, **post):
        """Get appointment status dashboard data."""
        appointee_id = post.get('appointee_id','')
        appointment_obj = request.env['appointment']
        is_manager_group = request.env.user.has_group('wk_appointment.appointment_manager_group')
        is_officer_group = request.env.user.has_group('wk_appointment.appointment_officer_group')
        is_appointee_group = request.env.user.has_group('wk_appointment.appointment_appointee_group')

        # checking if the logged in user is appointee, officer or manager
        if is_appointee_group and not is_manager_group and not is_officer_group:
            appointee_id = request.env.user.partner_id.id
            post['appointee_id'] = request.env.user.partner_id.id
        appointment_data = appointment_obj.get_appointment_status_data(post)
        status_labels = ["New", "Approved", "Pending", "Done", "Cancelled"]
        appointment_status_count_list = []
        for status in appointment_data['status_counts']:
            appointment_status_count_list.append(appointment_data['status_counts'][status])
        return {
            "status_labels": status_labels,
            "appointment_status_count_list": appointment_status_count_list,
            "appointment_status": appointment_data.get('status_counts'),
        }
