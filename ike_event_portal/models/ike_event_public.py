from odoo import models, fields, api, tools, _
from odoo.exceptions import AccessError


class IkeEventPublic(models.Model):
    _name = 'ike.event.public'
    _inherit = ['ike.event.base']
    _description = 'Event (public)'
    _auto = False
    # _table = 'ike_event'
    _log_access = True

    # Campos visibles para usuarios portal (readonly)
    name = fields.Char(readonly=False)
    event_date = fields.Datetime(readonly=False)
    service_id = fields.Many2one(readonly=False)
    sub_service_id = fields.Many2one(readonly=False)
    stage_id = fields.Many2one(readonly=False)
    user_id = fields.Many2one(readonly=False)
    location_label = fields.Char(readonly=False)
    destination_label = fields.Char(readonly=False)
    covered_amount = fields.Float(groups="base.group_no_one", readonly=False)
    user_code = fields.Char()

    @api.model
    def _get_fields(self):
        return ','.join('event.%s' % name for name, field in self._fields.items() if field.store and field.type not in ['many2many', 'one2many'])

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE or REPLACE VIEW %s as (
            SELECT
                %s
            FROM ike_event event
        )""" % (self._table, self._get_fields()))

    # ToDo
    # def write(self, vals):
    #     fields_names = list(vals.keys())
    #     event = self.env["ike.event"].sudo().browse(self.id)
    #     event._check_private_fields(fields_names)
    #     event.write(vals)
    #     return True
