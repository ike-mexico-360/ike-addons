/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { patch } from "@web/core/utils/patch";

patch(publicWidget.registry.PurchasePortalSidebar.prototype, {

    /**
     * @override
     */
    start() {
        const def = super.start(...arguments);
        this._bindDeclineButton();
        return def;
    },

    /**
     * @override
     */
    destroy() {
        this.$el.find('a[name="decline"]').off("click.purchase_decline");
        super.destroy(...arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    _bindDeclineButton() {
        // Apunta directo al nodo visible en el DOM según DevTools
        const $btn = this.$el.find('a[name="decline"]:not(.disabled)');
        console.log("Botón encontrado:", $btn.length); // Debe dar 1
        $btn.on("click.purchase_decline", this._onDeclineClick.bind(this));
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    _onDeclineClick(ev) {
        ev.preventDefault();
        const href = $(ev.currentTarget).attr("href");
        console.log("Decline clicked:", href);

        // $("#details").text("Cancelando...");

        // Tu lógica aquí
        // window.location.href = href;
    },
});
