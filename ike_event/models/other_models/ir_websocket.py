# -*- coding: utf-8 -*-

import re

from odoo import models


class IrWebsocket(models.AbstractModel):
    _inherit = "ir.websocket"

    def _build_bus_channel_list(self, channels):
        channels = list(channels)  # do not alter original list

        # Suppliers channels
        ike_supplier_ids = list()
        for channel in list(channels):
            if isinstance(channel, str):
                try:
                    match = re.findall(r'ike_channel_supplier_(\d+)', channel)
                    if match and int(match[0]) > 0:
                        channels.remove(channel)
                        ike_supplier_ids.append(int(match[0]))
                finally:
                    pass

        # Event channels
        ike_event_ids = list()
        for channel in list(channels):
            if isinstance(channel, str):
                try:
                    match = re.findall(r'ike_channel_event_(\d+)', channel)
                    if match and int(match[0]) > 0:
                        channels.remove(channel)
                        ike_event_ids.append(int(match[0]))
                finally:
                    pass

        if self.env.user._is_internal():
            # Filter Events Channels
            user_events = self.env["ike.event"].sudo().search([
                '|',
                ('id', 'in', ike_event_ids),
                '&',
                ('create_uid', '=', self.env.user.id),
                ('stage_ref', 'in', ['searching', 'assigned', 'in_progress']),
            ]).mapped('id')
            event_channels = ['ike_channel_event_' + str(event_id) for event_id in user_events]
            channels.extend([*event_channels])
        else:
            # Filter Event List Channel
            for channel in list(channels):
                if isinstance(channel, str):
                    if channel == 'IKE_CHANNEL_LIST':
                        channels.remove(channel)
        # Filter Suppliers channels
        if len(ike_supplier_ids):
            if self.env.user.has_group('base.group_erp_manager'):
                supplier_channels = ['ike_channel_supplier_' + str(supplier_id) for supplier_id in ike_supplier_ids]
            else:
                user_suppliers = self.env["res.partner.supplier_users.rel"].sudo().search([
                    ('user_id', '=', self.env.user.id),
                    ('supplier_id', 'in', ike_supplier_ids),
                ]).mapped('supplier_id.id')

                supplier_channels = ['ike_channel_supplier_' + str(supplier_id) for supplier_id in user_suppliers]
            channels.extend([*supplier_channels])
        return super()._build_bus_channel_list(channels)
