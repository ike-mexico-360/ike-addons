/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.trucksWidgetPortal = publicWidget.Widget.extend({
 selector: '#new-truck-form-container',
    events: {
        'submit form': '_onSubmitForm',
    },
    _onSubmitForm: function (ev) {
        // ev.preventDefault();
        // ev.stopPropagation();
        console.log("Form submitted");
    },
});

