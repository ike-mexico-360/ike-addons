from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class IkeSupportReport(models.Model):
    _name = 'ike.support.report'
    _description = 'Support Report'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Reference', required=True, readonly=True, copy=False, default='New')
    platform_id = fields.Many2one('ike.support.platform', 'Platform', required=True, index=True)
    failure_id = fields.Many2one('ike.support.failure', 'Failure', required=True, index=True)
    event = fields.Char('Event', required=True, help='Event / Purchase Order / Invoice')
    description = fields.Text('Description', required=True)
    image = fields.Image('Image', max_width=1920, max_height=1920)
    state = fields.Selection(
        selection=[
            ('open', 'Open'),
            ('in_progress', 'In Progress'),
            ('resolved', 'Resolved'),
        ],
        string='Status',
        required=True,
        copy=False,
        default='open',
        index=True,
        tracking=True,
    )
    can_change_state = fields.Boolean(compute='_compute_can_change_state')

    def _compute_can_change_state(self):
        can_change = self.env.user.has_group('ike_support.group_support_manager')
        for report in self:
            report.can_change_state = can_change

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('ike.support.report') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if 'state' in vals and not self.env.user.has_group('ike_support.group_support_manager'):
            raise AccessError(_('Only a Support Administrator can change the status.'))
        return super().write(vals)

    def action_open(self):
        self.write({'state': 'open'})

    def action_in_progress(self):
        self.write({'state': 'in_progress'})

    def action_resolved(self):
        self.write({'state': 'resolved'})
