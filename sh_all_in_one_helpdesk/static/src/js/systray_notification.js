/** @odoo-module **/

import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { session } from "@web/session";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
const { Component } = owl;
import { useState, useExternalListener } from "@odoo/owl";
import { user } from "@web/core/user";

export class UserNotificationMenu extends Component {
    setup() {
        this.orm = useService("orm");
        this.busService = this.env.services.bus_service;
        this.notifications = this._getActivityData();
        this.action = useService("action");
        this.state = useState({ custom_display: "none" });
        onWillStart(this.onWillStart);
        this._updateCounter();
    }
    onWindowClick(ev) {
        if (!ev.target.closest(".sh_bell_notification_contant")) {
          this.state.custom_display = "none";
        }
      }

    async onWillStart() {
        this.busService.addEventListener("notification", ({ detail: notifications }) => {
            for (var i = 0; i < notifications.length; i++) {
                var channel = notifications[i]["type"];
                if (channel == "sh.user.push.notification") {
                    this._getActivityData();
                    this._updateCounter();
                    // $(document).find(".o_searchview_input").click();
                    // $(document).click();
                    // Triggering a click on the search input using vanilla JS
                    const searchInput = document.querySelector(".o_searchview_input");
                    if (searchInput) {
                    searchInput.click();
                    }
                    // Simulating a click on the document using vanilla JS
                    document.dispatchEvent(new Event("click"));
                    
                }
            }
        });

        // const SHUserNotification = await this.orm.call("sh.user.push.notification", "has_bell_notification_enabled");
        // const bellNotification = document.querySelector(".js_bell_notification");
        // if (SHUserNotification) {
        //     if (SHUserNotification.has_bell_notification_enabled) {
        //         $(".js_bell_notification").removeClass("d-none");
        //     } else {
        //         $(".js_bell_notification").addClass("d-none");
        //     }
        // }

        // rpc(
        //     "/web/dataset/call_kw/sh.user.push.notification/has_bell_notification_enabled",
        //     {
        //       model: "sh.user.push.notification",
        //       method: "has_bell_notification_enabled",
        //       args: [],
        //       kwargs: {},
        //     }
        //   ).then(function (result) {
        //     const bellNotification = document.querySelector(".js_bell_notification");
        //     if (result.has_bell_notification_enabled) {
        //       bellNotification.classList.remove("d-none");
        //     } else {
        //       bellNotification.classList.add("d-none");
        //     }
        //   });
    }

    async _onPushNotificationClick(notification) {
        // fetch the data from the button otherwise fetch the ones from the parent (.o_mail_preview).
        var data = notification;
        var context = {};
        var self = this;

        await this.orm.call("sh.user.push.notification", "write", [data.id, { msg_read: true }], {});
        self._getActivityData();
        self._updateCounter();
        if (data.res_model != "")
            self.action.doAction(
                {
                    type: "ir.actions.act_window",
                    name: data.res_model,
                    res_model: data.res_model,
                    views: [
                        [false, "form"],
                        [false, "list"],
                    ],
                    search_view_id: [false],
                    domain: [["id", "=", data.res_id]],
                    res_id: data.res_id,
                    context: context,
                },
                {
                    clear_breadcrumbs: true,
                }
            );
    }

    async _onClickReadAllNotification(ev) {
        var self = this;
        const GetUserNotificationData = await this.orm.call("res.users", "systray_get_all_notifications", [], { context: session.user_context });
        self._notifications = GetUserNotificationData[0];
        const notificationData = GetUserNotificationData[0];
        for (let i = 0; i < notificationData.length; i++) {
            const each_data = notificationData[i];
            (async () => {
                await self.orm.call("sh.user.push.notification", "write", [each_data.id, { msg_read: true }], {});
                self._getActivityData();
                self._updateCounter();
            })();
        }
    }

    _onClickAllNotification(ev) {
        this.action.doAction(
            {
                type: "ir.actions.act_window",
                name: "Notifications",
                res_model: "sh.user.push.notification",
                views: [[false, "list"]],
                view_mode: "list",
                target: "current",
                domain: [["user_id", "=", user.userId]],
                // domain: [["user_id", "=", session.uid]],
            },
            {
                clear_breadcrumbs: true,
            }
        );
    }

    // _updateCounter() {
    //     var counter = this._counter;
    //     if (counter > 0) {
    //         $(".o_notification_counter").text(counter);
    //     } else {
    //         $(".o_notification_counter").text("");
    //     }
    // }
    _updateCounter() {
        const notificationCounter = document.querySelector(
          ".o_notification_counter"
        );
        if (notificationCounter) {
          const counter = this._counter;
          notificationCounter.textContent = counter > 0 ? counter : "";
        } else {
          console.warn("Notification counter element not found.");
        }
      }

    async _getActivityData() {
        var self = this;
        const GetActivityData = await this.orm.call("res.users", "systray_get_notifications", [], { context: session.user_context });
        self._notifications = GetActivityData[0];
        self._counter = GetActivityData[1];
        if (GetActivityData && GetActivityData[0]) {
            GetActivityData[0].forEach((each_data) => {
                each_data["datetime"] = self.formatRelativeTime(each_data["datetime"]);
            });
        }
        self._updateCounter();
        return GetActivityData;
    }

    _updateActivityPreview() {
        this.notifications = this._notifications;
        const dropdownItems = document.querySelector(
          ".o_notification_systray_dropdown_items"
        );
        if (dropdownItems) {
          dropdownItems.classList.remove("d-none");
        }
      }

    async _onActivityMenuShow() {
        if (this.state.custom_display == "none") {
          this.state.custom_display = "block";
        } else {
          this.state.custom_display = "none";
        }
    
        this.render(true);
        await this._updateActivityPreview();
    }

    _onActivityActionClick(ev) {
        ev.stopPropagation();
        var actionXmlid = $(ev.currentTarget).data("action_xmlid");
        this.do_action(actionXmlid);
    }

    /**
     * Get particular model view to redirect on click of activity scheduled on that model.
     * @private
     * @param {string} model
     */
    _getActivityModelViewID(model) {
        return rpc.query({
            model: model,
            method: "get_activity_view_id",
        });
    }

    // formatRelativeTime(dateTime) {
    
    //     console.log("\n\n\n\n\n\n dateTime>>> ", dateTime);
    //     const now = new Date();
    //     console.log("\n\n\n\n\n\n now>>> ", now);
    //     // Convert dateTime to a Date object
    //     dateTime = new Date(dateTime);

    //     const diffInSeconds = Math.floor((now - dateTime) / 1000);

    //     if (diffInSeconds < 60) {
    //         return _t("less than a minute ago");
    //     } else if (diffInSeconds < 120) {
    //         return _t("about a minute ago");
    //     } else if (diffInSeconds < 3600) {
    //         return _t(`${Math.floor(diffInSeconds / 60)} minutes ago`);
    //     } else if (diffInSeconds < 7200) {
    //         return _t("about an hour ago");
    //     } else if (diffInSeconds < 86400) {
    //         return _t(`${Math.floor(diffInSeconds / 3600)} hours ago`);
    //     } else if (diffInSeconds < 172800) {
    //         return _t("a day ago");
    //     } else if (diffInSeconds < 2592000) {
    //         return _t(`${Math.floor(diffInSeconds / 86400)} days ago`);
    //     } else if (diffInSeconds < 5184000) {
    //         return _t("about a month ago");
    //     } else if (diffInSeconds < 31536000) {
    //         return _t(`${Math.floor(diffInSeconds / 2592000)} months ago`);
    //     } else if (diffInSeconds < 63072000) {
    //         return _t("about a year ago");
    //     } else {
    //         return _t(`${Math.floor(diffInSeconds / 31536000)} years ago`);
    //     }
    // }

    formatRelativeTime(dateTime) {
        const now = new Date();
        const targetTime = new Date(dateTime);
        
        // Adjust for the time zone difference
        const timeZoneOffset = now.getTimezoneOffset() - targetTime.getTimezoneOffset();
        targetTime.setMinutes(targetTime.getMinutes() + timeZoneOffset);
    
        // Add 5 hours and 30 minutes
        targetTime.setHours(targetTime.getHours() + 5);
        targetTime.setMinutes(targetTime.getMinutes() + 30);
    
        // Calculate the time difference in seconds
        const diffInSeconds = Math.floor((now - targetTime) / 1000);
    
        // For example:
        if (diffInSeconds < 60) {
            return _t("less than a minute ago");
        } else if (diffInSeconds < 120) {
            return _t("about a minute ago");
        } else if (diffInSeconds < 3600) {
            return _t(`${Math.floor(diffInSeconds / 60)} minutes ago`);
        } else if (diffInSeconds < 7200) {
            return _t("about an hour ago");
        } else if (diffInSeconds < 86400) {
            return _t(`${Math.floor(diffInSeconds / 3600)} hours ago`);
        } else if (diffInSeconds < 172800) {
            return _t("a day ago");
        } else if (diffInSeconds < 2592000) {
            return _t(`${Math.floor(diffInSeconds / 86400)} days ago`);
        } else if (diffInSeconds < 5184000) {
            return _t("about a month ago");
        } else if (diffInSeconds < 31536000) {
            return _t(`${Math.floor(diffInSeconds / 2592000)} months ago`);
        } else if (diffInSeconds < 63072000) {
            return _t("about a year ago");
        } else {
            return _t(`${Math.floor(diffInSeconds / 31536000)} years ago`);
        }
    }
    
}

UserNotificationMenu.template = "mail.systray.UserNotificationMenu";

export const systrayItem = {
    Component: UserNotificationMenu,
};

registry.category("systray").add("UserNotificationMenu", systrayItem);
