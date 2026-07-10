/** @odoo-module **/

import {registry} from "@web/core/registry";
import {formatMonetary} from "@web/views/fields/formatters";

const tierValidationField = registry.category("fields").get("form.tier_validation");
const relatedFieldNames = new Set(
    tierValidationField.relatedFields.map((field) => field.name)
);

for (const field of [
    {name: "increase_currency_id", type: "many2one", relation: "res.currency"},
    {name: "increase_requested_amount", type: "monetary"},
    {name: "increase_approved_amount", type: "monetary"},
]) {
    if (!relatedFieldNames.has(field.name)) {
        tierValidationField.relatedFields.push(field);
    }
}

tierValidationField.component.prototype.formatIncreaseAmount = function (
    amount,
    currency
) {
    const currencyId = Array.isArray(currency) ? currency[0] : currency;
    return formatMonetary(amount, {currencyId});
};

tierValidationField.component.prototype.showIncreaseAmounts = function () {
    return this.props.record.resModel === "ike.event.authorized.amount.request";
};
