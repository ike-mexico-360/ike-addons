/** @odoo-module **/
import { registry } from "@web/core/registry";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { useInputField } from "@web/views/fields/input_field_hook";

function literals(mask) {
    return new Set([...mask].filter((ch) => ch !== "#" && ch !== "*"));
}

function applyMask(data, mask) {
    if (!data || !mask) return data || "";
    let result = "", di = 0;
    for (const m of mask) {
        if (di >= data.length) break;
        if (m === "#") result += data[di++];
        // El asterisco en la máscara oculta el dato visualmente pero di++ avanza el dato real
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
        super.setup();
        // Mantenemos el valor real en una variable interna de la clase
        this.currentRawValue = this.props.record.data[this.props.name] || "";
        
        this.inputRef = useInputField({
            getValue: () => this.maskedValue,
            parse: (v) => this.parse(v),
        });
    }

    get _mask() {
        return this.props.record.data[this.props.maskField || "x_display_mask"] || "";
    }

    get maskedValue() {
        const mask = this._mask;
        const val = this.props.record.data[this.props.name] || "";
        if (!mask) return val;
        // Siempre enmascaramos basándonos en el valor real del registro
        return applyMask(val, mask);
    }

    parse(value) {
        // Al guardar, usamos el valor real acumulado en lugar de intentar limpiar el input enmascarado
        const data = this.currentRawValue;
        const pattern = this.props.record.data[this.props.patternField || "x_validation_pattern"];
        if (data && pattern && !new RegExp(pattern).test(data)) {
            throw new Error("El valor ingresado no cumple el patrón");
        }
        return data;
    }

    onInput(ev) {
        const mask = this._mask;
        const input = ev.target;
        if (!mask) {
            this.currentRawValue = input.value;
            this.props.record.update({ [this.props.name]: this.currentRawValue });
            return;
        }

        const lits = literals(mask);
        const selectionStart = input.selectionStart;
        const val = input.value;

        // --- LÓGICA DE RECONSTRUCCIÓN DEL VALOR REAL ---
        let newRawValue = "";
        let visualIdx = 0;
        let rawIdx = 0;

        for (const m of mask) {
            if (visualIdx >= val.length) break;
            const char = val[visualIdx];

            if (m === "#" || m === "*") {
                // Si el carácter visual es un asterisco, significa que el usuario no lo cambió
                // (o escribió un asterisco), por lo que mantenemos el valor real previo.
                if (char === "*") {
                    newRawValue += this.currentRawValue[rawIdx] || "";
                } else {
                    newRawValue += char;
                }
                rawIdx++;
                visualIdx++;
            } else {
                // Es un literal (guion, etc.), lo saltamos visualmente
                visualIdx++;
            }
        }
        // Manejar caracteres sobrantes si el usuario pegó texto más largo que la máscara
        if (visualIdx < val.length && rawIdx >= mask.replace(/[^#*]/g, "").length) {
             newRawValue += val.slice(visualIdx);
        }

        this.currentRawValue = newRawValue;

        // Calcular posición del cursor antes de renderizar la máscara
        const before = [...val.slice(0, selectionStart)].filter((ch) => !lits.has(ch)).length;
        
        // Aplicar máscara visual
        const masked = applyMask(this.currentRawValue, mask);
        input.value = masked;

        // Reposicionar cursor
        const pos = cursorAfter(masked, lits, before);
        input.setSelectionRange(pos, pos);

        // Actualizar Odoo con el valor REAL
        this.props.record.update({ [this.props.name]: this.currentRawValue });
    }

    onKeydown(ev) {
        // En este enfoque, onInput maneja la reconstrucción basándose en lo que queda en el input
        // tras el borrado, por lo que no es estrictamente necesario interceptar Backspace aquí
        // a menos que quieras comportamientos especiales de salto de literales.
    }
}

RegexValidatorField.template = "custom_master_catalog.IkeRegexValidatorField";
RegexValidatorField.props = {
    ...CharField.props,
    maskField: { type: String, optional: true },
    patternField: { type: String, optional: true },
};

export const regexValidatorField = {
    ...charField,
    component: RegexValidatorField,
        extractProps() {
        const props = charField.extractProps(...arguments);
        const { attrs } = arguments[0] || {};

        return {
            ...props,
            maskField: attrs?.mask_field,
            patternField: attrs?.pattern_field,
        };
    }
};

registry.category("fields").add("ike_regex_validator_field", regexValidatorField);