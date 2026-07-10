from odoo import api, fields, models


class TierReview(models.Model):
    _inherit = "tier.review"

    increase_currency_id = fields.Many2one(
        comodel_name="res.currency",
        compute="_compute_increase_amounts",
    )
    increase_requested_amount = fields.Monetary(
        string="Requested Amount",
        currency_field="increase_currency_id",
        compute="_compute_increase_amounts",
    )
    increase_approved_amount = fields.Monetary(
        string="Approved Amount",
        currency_field="increase_currency_id",
        compute="_compute_increase_amounts",
    )

    @api.depends("model", "res_id", "status")
    def _compute_increase_amounts(self):
        request_model = "ike.event.authorized.amount.request"
        for review in self:
            review.increase_currency_id = False
            review.increase_requested_amount = 0.0
            review.increase_approved_amount = 0.0
            if review.model != request_model or not review.res_id:
                continue

            request = self.env[request_model].browse(review.res_id).exists()
            if not request:
                continue
            review.increase_currency_id = request.currency_id
            review.increase_requested_amount = request.requested_amount
            review.increase_approved_amount = (
                request.requested_amount
                if review.status == "approved" and request.state == "approved"
                else 0.0
            )

            self.env.cr.execute(
                """
                SELECT tracking.old_value_float
                  FROM mail_tracking_value AS tracking
                  JOIN mail_message AS message
                    ON message.id = tracking.mail_message_id
                  JOIN ir_model_fields AS field
                    ON field.id = tracking.field_id
                 WHERE message.model = %s
                   AND message.res_id = %s
                   AND message.author_id = %s
                   AND field.name = 'requested_amount'
                 ORDER BY message.id, tracking.id
                 LIMIT 1
                """,
                (request_model, request.id, request.authorizer_id.partner_id.id),
            )
            first_adjustment = self.env.cr.fetchone()
            if first_adjustment:
                review.increase_requested_amount = first_adjustment[0]
