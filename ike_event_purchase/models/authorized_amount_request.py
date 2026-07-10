from markupsafe import Markup
from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class IkeEventAuthorizedAmountRequest(models.Model):
    _name = "ike.event.authorized.amount.request"
    _description = "Event Authorized Amount Increase Request"
    _inherit = ["mail.thread", "mail.activity.mixin", "tier.validation"]
    _order = "id desc"

    _state_from = ["draft"]
    _state_to = ["approved"]
    _cancel_state = "cancelled"
    _tier_validation_manual_config = False

    def _add_tier_validation_reviews(self, node, params):
        reviews_node = super()._add_tier_validation_reviews(node, params)
        comment_node = reviews_node.xpath(".//field[@name='comment']")[0]
        comment_node.addprevious(
            etree.Element("field", name="increase_requested_amount")
        )
        comment_node.addprevious(
            etree.Element("field", name="increase_approved_amount")
        )
        return reviews_node

    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    purchase_order_id = fields.Many2one(
        comodel_name="purchase.order",
        string="Cost Review",
        required=True,
        readonly=True,
        ondelete="cascade",
        tracking=True,
    )
    event_id = fields.Many2one(
        comodel_name="ike.event",
        related="purchase_order_id.x_event_id",
        string="Event",
        store=True,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        related="purchase_order_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        related="purchase_order_id.currency_id",
        store=True,
        readonly=True,
    )
    requester_id = fields.Many2one(
        comodel_name="res.users",
        string="Requested by",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    authorizer_id = fields.Many2one(
        comodel_name="res.users",
        string="Authorizer",
        required=True,
        tracking=True,
        domain=lambda self: [
            (
                "groups_id",
                "in",
                self.env.ref(
                    "custom_master_catalog.custom_group_ccc_boss"
                ).id,
            )
        ],
    )
    current_authorized_amount = fields.Monetary(
        string="Current Authorized Amount",
        required=True,
        readonly=True,
        tracking=True,
    )
    disputed_amount = fields.Monetary(
        string="Disputed Amount",
        required=True,
        readonly=True,
        tracking=True,
    )
    requested_amount = fields.Monetary(
        string="Requested Authorized Amount",
        required=True,
        tracking=True,
    )
    reason = fields.Text(string="Reason", required=True, tracking=True)
    state = fields.Selection(
        selection=[
            ("draft", "Pending Authorization"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        required=True,
        default="draft",
        copy=False,
        tracking=True,
    )
    approved_by = fields.Many2one(
        comodel_name="res.users",
        string="Authorized by",
        readonly=True,
        copy=False,
        tracking=True,
    )
    approved_date = fields.Datetime(
        string="Authorization Date",
        readonly=True,
        copy=False,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            order = self.env["purchase.order"].browse(vals.get("purchase_order_id"))
            if order:
                vals.update(
                    {
                        "current_authorized_amount": order.x_dispute_authorized_amount,
                        "disputed_amount": order.amount_untaxed_dispute,
                        "requester_id": self.env.user.id,
                    }
                )
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = sequence.next_by_code(
                    "ike.event.authorized.amount.request"
                ) or _("New")
        records = super().create(vals_list)
        for record in records:
            record._check_requester_group()
            record._check_business_conditions()
            record.message_subscribe(
                partner_ids=(record.requester_id | record.authorizer_id)
                .mapped("partner_id")
                .ids
            )
        return records

    def write(self, vals):
        protected_fields = {
            "purchase_order_id",
            "event_id",
            "company_id",
            "currency_id",
            "requester_id",
            "current_authorized_amount",
            "disputed_amount",
        }
        if protected_fields & vals.keys():
            raise UserError(_("The source values of an increase request cannot be changed."))
        if "state" in vals:
            for record in self:
                if vals["state"] == "approved" and (
                    self.env.user != record.authorizer_id
                    or record.validation_status != "validated"
                ):
                    raise UserError(_("Only a validated request can be approved."))
                if vals["state"] == "rejected" and (
                    self.env.user != record.authorizer_id
                    or record.validation_status != "rejected"
                ):
                    raise UserError(_("Only the selected CCC Leader can reject this request."))
                if vals["state"] == "cancelled" and self.env.user not in (
                    record.requester_id | record.authorizer_id
                ) and not self.env.user.has_group("base.group_system"):
                    raise UserError(
                        _("Only the requester or authorizer can cancel this request.")
                    )
        if "requested_amount" in vals:
            for record in self.filtered("review_ids"):
                if self.env.user != record.authorizer_id:
                    raise UserError(
                        _("Only the selected CCC Leader can edit the requested amount.")
                    )
        result = super().write(vals)
        if {"authorizer_id", "requested_amount", "purchase_order_id"} & vals.keys():
            for record in self:
                record._check_business_conditions()
        return result

    def unlink(self):
        if any(record.state != "draft" or record.review_ids for record in self):
            raise UserError(
                _("Only requests without an authorization process can be deleted.")
            )
        return super().unlink()

    @api.constrains("authorizer_id")
    def _check_authorizer_group(self):
        leader_group = self.env.ref(
            "custom_master_catalog.custom_group_ccc_boss"
        )
        for record in self:
            if record.authorizer_id and leader_group not in record.authorizer_id.groups_id:
                raise ValidationError(_("The authorizer must have the CCC Leader role."))

    @api.constrains("purchase_order_id", "state")
    def _check_single_pending_request(self):
        for record in self.filtered(lambda item: item.state == "draft"):
            if self.search_count(
                [
                    ("purchase_order_id", "=", record.purchase_order_id.id),
                    ("state", "=", "draft"),
                ]
            ) > 1:
                raise ValidationError(
                    _("Only one pending increase request is allowed per cost review.")
                )

    @api.constrains("requested_amount", "current_authorized_amount", "disputed_amount")
    def _check_requested_amount(self):
        for record in self:
            rounding = record.currency_id.rounding or 0.01
            if (
                float_compare(
                    record.requested_amount,
                    record.current_authorized_amount,
                    precision_rounding=rounding,
                )
                < 0
            ):
                raise ValidationError(
                    _("The requested amount cannot be less than the current authorized amount.")
                )
            if (
                float_compare(
                    record.requested_amount,
                    record.disputed_amount,
                    precision_rounding=rounding,
                )
                < 0
            ):
                raise ValidationError(
                    _("The requested amount must cover the amount disputed by the supplier.")
                )

    def _check_requester_group(self):
        allowed_groups = (
            "custom_master_catalog.custom_group_ccc_analyst",
            "custom_master_catalog.custom_group_ccc_coordinator",
            "custom_master_catalog.custom_group_ccc_boss",
            "base.group_system",
        )
        if not any(self.env.user.has_group(group) for group in allowed_groups):
            raise UserError(_("Only CCC users can request an authorized amount increase."))

    def _check_business_conditions(self):
        self.ensure_one()
        order = self.purchase_order_id
        if not order.x_event_id:
            raise ValidationError(_("The cost review must be linked to an event."))
        if order.x_dispute_state != "submitted":
            raise ValidationError(
                _("An increase can only be requested for a submitted dispute.")
            )
        rounding = self.currency_id.rounding or 0.01
        if (
            float_compare(
                order.amount_untaxed_dispute,
                order.x_dispute_authorized_amount,
                precision_rounding=rounding,
            )
            <= 0
        ):
            raise ValidationError(
                _("The disputed amount does not exceed the authorized amount.")
            )
        if (
            float_compare(
                self.requested_amount,
                order.x_dispute_authorized_amount,
                precision_rounding=rounding,
            )
            < 0
        ):
            raise ValidationError(
                _("The requested amount cannot be less than the current authorized amount.")
            )
        if (
            float_compare(
                self.requested_amount,
                order.amount_untaxed_dispute,
                precision_rounding=rounding,
            )
            < 0
        ):
            raise ValidationError(
                _("The requested amount must cover the current supplier dispute.")
            )
        self._check_authorizer_group()
        self._check_requested_amount()

    def request_validation(self):
        for record in self:
            record._check_requester_group()
            record._check_business_conditions()
            duplicate = self.search(
                [
                    ("purchase_order_id", "=", record.purchase_order_id.id),
                    ("state", "=", "draft"),
                    ("review_ids", "!=", False),
                    ("id", "!=", record.id),
                ],
                limit=1,
            )
            if duplicate:
                raise UserError(
                    _("There is already a pending increase request: %s", duplicate.name)
                )
        reviews = super().request_validation()
        if not reviews:
            raise UserError(_("No authorization level was configured for this request."))
        for record in self:
            record._schedule_authorizer_activity()
            record.purchase_order_id.message_post(
                body=Markup(
                    _(
                        "Authorized amount increase %(request)s requested: "
                        "%(current)s → %(requested)s.",
                        request=record.name,
                        current=record.currency_id.format(record.current_authorized_amount),
                        requested=record.currency_id.format(record.requested_amount),
                    )
                ),
                partner_ids=record.authorizer_id.partner_id.ids,
                subtype_xmlid="mail.mt_comment",
            )
        return reviews

    def _validate_tier(self, tiers=False):
        result = super()._validate_tier(tiers)
        for record in self.filtered(lambda item: item.validation_status == "validated"):
            record._approve_amount_increase()
        return result

    def _check_state_conditions(self, vals):
        if self.env.context.get("skip_amount_increase_tier_state_check"):
            return False
        return super()._check_state_conditions(vals)

    def _rejected_tier(self, tiers=False):
        result = super()._rejected_tier(tiers)
        for record in self.filtered(lambda item: item.validation_status == "rejected"):
            record.with_context(skip_validation_check=True).write({"state": "rejected"})
            record._finish_authorizer_activity(_("Increase request rejected"))
            record._notify_requester(
                _(
                    "The authorized amount increase request %(request)s was rejected.",
                    request=record.name,
                )
            )
        return result

    def restart_validation(self):
        self._finish_authorizer_activity(_("Authorization restarted"))
        return super().restart_validation()

    def action_cancel(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Only a pending request can be cancelled."))
            allowed_users = record.requester_id | record.authorizer_id
            if self.env.user not in allowed_users and not self.env.user.has_group(
                "base.group_system"
            ):
                raise UserError(_("Only the requester or authorizer can cancel this request."))
        self._finish_authorizer_activity(_("Increase request cancelled"))
        return self.with_context(skip_validation_check=True).write({"state": "cancelled"})

    def _approve_amount_increase(self):
        self.ensure_one()
        if self.state != "draft":
            return
        if self.env.user != self.authorizer_id or not self.env.user.has_group(
            "custom_master_catalog.custom_group_ccc_boss"
        ):
            raise UserError(_("Only the selected CCC Leader can authorize this request."))
        self._check_business_conditions()
        previous_amount = self.purchase_order_id.x_dispute_authorized_amount
        self.with_context(
            skip_validation_check=True,
            skip_amount_increase_tier_state_check=True,
        ).write(
            {
                "state": "approved",
                "approved_by": self.env.user.id,
                "approved_date": fields.Datetime.now(),
            }
        )
        self.purchase_order_id.sudo().with_context(
            authorized_dispute_amount_update=True
        ).write(
            {"x_dispute_authorized_amount": self.requested_amount}
        )
        body = _(
            "Authorized amount increase %(request)s approved: %(previous)s → %(new)s.",
            request=self.name,
            previous=self.currency_id.format(previous_amount),
            new=self.currency_id.format(self.requested_amount),
        )
        self.purchase_order_id.message_post(
            body=Markup(body),
            partner_ids=self.requester_id.partner_id.ids,
            subtype_xmlid="mail.mt_comment",
        )
        self._finish_authorizer_activity(_("Increase request approved"))
        self._notify_requester(body)

    def _schedule_authorizer_activity(self):
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        for record in self:
            existing = record.activity_ids.filtered(
                lambda activity: activity.user_id == record.authorizer_id
                and activity.activity_type_id == activity_type
            )
            if not existing:
                record.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=record.authorizer_id.id,
                    summary=_("Authorize event amount increase"),
                    note=_(
                        "Review request %(request)s for event %(event)s.",
                        request=record.name,
                        event=record.event_id.display_name,
                    ),
                )

    def _finish_authorizer_activity(self, feedback):
        activity_type = self.env.ref("mail.mail_activity_data_todo")
        for record in self:
            record.activity_ids.filtered(
                lambda activity: activity.user_id == record.authorizer_id
                and activity.activity_type_id == activity_type
            ).action_feedback(feedback=feedback)

    def _notify_requester(self, body):
        for record in self:
            record.message_post(
                body=Markup(body),
                partner_ids=record.requester_id.partner_id.ids,
                subtype_xmlid="mail.mt_comment",
            )


class TierDefinition(models.Model):
    _inherit = "tier.definition"

    @api.model
    def _get_tier_validation_model_names(self):
        model_names = super()._get_tier_validation_model_names()
        model_names.append("ike.event.authorized.amount.request")
        return model_names
