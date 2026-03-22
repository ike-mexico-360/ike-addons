import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { useInputField } from "@web/views/fields/input_field_hook";
import { Component, xml } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

function literals(mask) {
    return new Set([...mask].filter((ch) => ch !== "#" && ch !== "*"));
}

function strip(value, lits) {
    return [...value].filter((ch) => !lits.has(ch)).join("");
}

function applyMask(data, mask) {
    if (!data || !mask) return data || "";
    let result = "", di = 0;
    for (const m of mask) {
        if (di >= data.length) break;
        if (m === "#") result += data[di++];
        else if (m === "*") { result += "*"; di++; }
        else result += m;
    }
    return result;
 }

function cursorAfter(masked, lits, count) {
    let seen = 0, pos = masked.length;
    for (let i = 0; i < masked.length; i++) {
        if (!lits.has(masked[i])) seen++;
        if (seen === count) {
            pos = i + 1;
            while (pos < masked.length && lits.has(masked[pos])) pos++;
            break;
        }
    }
    return pos;
}

export class RegexValidatorField extends CharField {
    setup() {
        this.inputRef = useInputField({
            getValue: () => this.maskedValue,
            parse: (v) => this.parse(v),
        });
    }

    get _mask() {
        return this.props.record.data[this.props.maskField || "x_display_mask"] || "";
    }

    get formattedValue() {
        return this.props.record.data[this.props.name] || "";
    }

    get maskedValue() {
        const mask = this._mask;
        if (!mask) return this.formattedValue;
        const lits = literals(mask);
        return applyMask(strip(this.formattedValue, lits), mask);
    }

    _restoreRaw(stripped) {
        const mask = this._mask;
        if (!mask || !stripped.includes("*")) return stripped;
        const lits = literals(mask);
        const storedRaw = strip(this.formattedValue, lits);
        let result = "", di = 0;
        for (const m of mask) {
            if (lits.has(m)) continue;
            if (di >= stripped.length) break;
            result += (m === "*" && stripped[di] === "*") ? (storedRaw[di] || "") : stripped[di];
            di++;
        }
        return result;
    }

    parse(value) {
        const mask = this._mask;
        const lits = literals(mask);
        const raw = super.parse(this._restoreRaw(strip(value, lits)));
        const pattern = this.props.record.data[this.props.patternField || "x_validation_pattern"];
        if (raw && pattern && !new RegExp(pattern).test(raw)) {
            throw new Error("El valor ingresado no cumple el patrón");
        }
        return raw;
    }

    onInput(ev) {
        const mask = this._mask;
        if (!mask) return;
        const input = ev.target;
        const lits = literals(mask);
        const before = [...input.value.slice(0, input.selectionStart)].filter((ch) => !lits.has(ch)).length;
        const stripped = strip(input.value, lits);
        const data = this._restoreRaw(stripped);
        const masked = applyMask(data, mask);
        input.value = masked;
        const pos = cursorAfter(masked, lits, before);
        input.setSelectionRange(pos, pos);
        this.props.record.update({ [this.props.name]: data });
    }

    onKeydown(ev) {
        if (ev.key !== "Backspace" && ev.key !== "Delete") return;
        const mask = this._mask;
        if (!mask) return;
        const input = ev.target;
        const cur = input.selectionStart;
        const val = input.value;
        const lits = literals(mask);

        if (ev.key === "Backspace" && cur > 0 && lits.has(val[cur - 1])) {
            ev.preventDefault();
            const before = [...val.slice(0, cur)].filter((ch) => !lits.has(ch)).length;
            if (before === 0) return;
            const raw = this._restoreRaw(strip(val, lits));
            const newData = raw.slice(0, before - 1) + raw.slice(before);
            const masked = applyMask(newData, mask);
            input.value = masked;
            const pos = cursorAfter(masked, lits, before - 1);
            input.setSelectionRange(pos, pos);
            this.props.record.update({ [this.props.name]: newData });

        } else if (ev.key === "Delete" && cur < val.length && lits.has(val[cur])) {
            ev.preventDefault();
            let next = cur;
            while (next < val.length && lits.has(val[next])) next++;
            if (next >= val.length) return;
            const before = [...val.slice(0, next)].filter((ch) => !lits.has(ch)).length;
            const raw = this._restoreRaw(strip(val, lits));
            const newData = raw.slice(0, before) + raw.slice(before + 1);
            input.value = applyMask(newData, mask);
            input.setSelectionRange(cur, cur);
            this.props.record.update({ [this.props.name]: newData });
        }
    }

    onBlur(ev) {
        const mask = this._mask;
        if (!mask) return;
        const input = ev.target;
        const lits = literals(mask);
        input.value = applyMask(strip(input.value, lits), mask);
    }
}

RegexValidatorField.template = "custom_master_catalog.RegexValidatorField";
RegexValidatorField.props = {
    ...CharField.props,
    maskField: { type: String, optional: true },
    patternField: { type: String, optional: true },
};

export const regexValidatorField = {
    ...charField,
    component: RegexValidatorField,
    extractProps: (fieldInfo) => {
        const props = { ...charField.extractProps?.(fieldInfo) };
        if (fieldInfo.attrs.mask_field) props.maskField = fieldInfo.attrs.mask_field;
        if (fieldInfo.attrs.pattern_field) props.patternField = fieldInfo.attrs.pattern_field;
        return props;
    },
};
registry.category("fields").add("regex_validator_field", regexValidatorField);

class MaskedField extends Component {
    static template = xml`<span t-esc="maskedValue" class="o_masked_field"/>`;
    static props = {
        ...standardFieldProps,
        maskField: { type: String, optional: true },
    };
    get maskedValue() {
        const value = this.props.record.data[this.props.name] || "";
        const maskFieldName = this.props.maskField || "x_display_mask";
        const mask = this.props.record.data[maskFieldName] || "";
        return applyMask(value, mask);
    }
}

export const maskedField = {
    component: MaskedField,
    displayName: "Masked Field",
    supportedTypes: ["char"],
    extractProps: ({ attrs }) => ({
        maskField: attrs.mask_field || "x_display_mask",
    }),
};
registry.category("fields").add("masked", maskedField);
