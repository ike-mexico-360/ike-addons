import { Message } from "@mail/core/common/message_model";
import { Record } from "@mail/core/common/record";
import { patch } from "@web/core/utils/patch";

patch(Message.prototype, {
    setup() {
        super.setup();
        this.isEmpty = Record.attr(false, {
            /** @this {import("models").Message} */
            compute() {
                return this.computeIsEmpty();
            },
        });
    },
    computeIsEmpty() {
        return (
            this.isBodyEmpty &&
            this.attachment_ids.length === 0 &&
            this.trackingValues.length === 0 &&
            !this.subtype_description &&
            this.o2mTrackings.length === 0
        );
    },
});