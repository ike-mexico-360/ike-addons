from odoo import fields, models, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_default_purchase_project_id = fields.Many2one(
        comodel_name='project.project',
        string='Default Purchase Project',
        help="Technical: Default purchase project linked to the company at consolidate and send SAP data.",
        ondelete='restrict',
        tracking=True,
    )

    @api.model
    def x_get_ike_company_language(self):
        country_code = self.env.company.country_id.code
        if country_code == 'MX':
            return 'es_MX'
        elif country_code == 'CO':
            return 'es_CO'
        else:
            return 'en_US'
