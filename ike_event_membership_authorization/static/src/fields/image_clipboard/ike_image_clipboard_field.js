/** @odoo-module **/
import { ImageField } from "@web/views/fields/image/image_field";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";

patch(ImageField.prototype, {
    setup() {
        super.setup(...arguments);

        const onPaste = (event) => {
            if (this.props.readonly) return;

            const items = event.clipboardData && event.clipboardData.items;
            if (!items) return;

            for (const item of items) {
                if (item.type.startsWith("image/")) {
                    const file = item.getAsFile();
                    if (!file) continue;

                    const reader = new FileReader();
                    reader.onload = (e) => {
                        const base64 = e.target.result.split(",")[1];
                        this.props.record.update({ [this.props.name]: base64 });
                    };
                    reader.readAsDataURL(file);
                    event.preventDefault();
                    break;
                }
            }
        };

        onMounted(() => document.addEventListener("paste", onPaste));
        onWillUnmount(() => document.removeEventListener("paste", onPaste));
    },
});
