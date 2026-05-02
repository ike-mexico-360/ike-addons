from odoo import models, fields, _ 


class IkeEvenPhoneWizard(models.Model):
    _name="ike.event.phone.wizard"
    description="view other phonesres partner"

    ike_event_supplier_id = fields.Many2one(
        'ike.event.supplier',
        string='Supplier',
        )

    x_phone_p1 = fields.Char(related="ike_event_supplier_id.supplier_id.x_phone_p1")
    x_phone_p2 = fields.Char(related="ike_event_supplier_id.supplier_id.x_phone_p2")
    x_phone_p3 = fields.Char(related="ike_event_supplier_id.supplier_id.x_phone_p3")
    x_phone_p4 = fields.Char(related="ike_event_supplier_id.supplier_id.x_phone_p4")
    x_phone_p5 = fields.Char(related="ike_event_supplier_id.supplier_id.x_phone_p5")
    
    x_phone_p1_classification_id = fields.Many2one(related="ike_event_supplier_id.supplier_id.x_phone_p1_classification_id")
    x_phone_p2_classification_id = fields.Many2one(related="ike_event_supplier_id.supplier_id.x_phone_p2_classification_id")
    x_phone_p3_classification_id = fields.Many2one(related="ike_event_supplier_id.supplier_id.x_phone_p3_classification_id")
    x_phone_p4_classification_id = fields.Many2one(related="ike_event_supplier_id.supplier_id.x_phone_p4_classification_id")
    x_phone_p5_classification_id = fields.Many2one(related="ike_event_supplier_id.supplier_id.x_phone_p5_classification_id")

    def action_close_wizard(self):
        self.ensure_one()
        return self.ike_event_supplier_id.action_open_travel_tracking()