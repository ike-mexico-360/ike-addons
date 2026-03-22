import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { HtmlField, htmlField } from "@web/views/fields/html/html_field";

import { onMounted, useRef, useState } from "@odoo/owl";

export class IkeHtmlField extends HtmlField {
    setup() {
        super.setup();
        this.contentRef = useRef("content");
        this.state = useState({
            isExpanded: false,
            hasMoreLines: false
        });

        onMounted(() => {
            this.checkLineCount();
        });
    }
    checkLineCount() {
        const el = this.contentRef.el;
        if (!el) return;

        const fullHeight = el.scrollHeight;

        // const lineHeight = parseInt(window.getComputedStyle(el).lineHeight);
        const sevenLinesHeight = 120;

        if (fullHeight > sevenLinesHeight) {
            this.state.hasMoreLines = true;
        }
    }
    toggleExpand() {
        this.state.isExpanded = !this.state.isExpanded;
    }
    get buttonText() {
        return this.state.isExpanded ? _t("Show Less") : _t("Show More");
    }
}

IkeHtmlField.template = "ike_event.IkeHtmlField";

export const ikeHtmlField = {
    ...htmlField,
    component: IkeHtmlField,
};

registry.category("fields").add("ike_html", ikeHtmlField);