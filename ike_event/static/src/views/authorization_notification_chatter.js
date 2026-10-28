/** @odoo-module **/

import { ChatWindow } from "@mail/core/common/chat_window";
import { patch } from "@web/core/utils/patch";

// This is the Discuss popup shown after clicking an inbox notification, not
// the form chatter. Only threads containing the authorization marker hide the
// composer; every other ChatWindow keeps its normal behaviour.
patch(ChatWindow.prototype, {
    get isAuthorizationNotificationReadonly() {
        return this.thread?.messages?.some(
            (message) => message.body?.includes('o-ike-authorization-notification')
        ) || false;
    },
});
