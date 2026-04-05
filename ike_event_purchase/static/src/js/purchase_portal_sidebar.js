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
        this._hideElements();
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
    
    _hideElements() {
        const $buttons = this.$el.find('a[name="accept"], a[name="decline"], button[name="accept"]');
        const $container = $buttons.closest('.flex-grow-1.d-flex.gap-2');
        
        $container.removeClass('d-flex').hide();
        
        const $navspy = this.$el.find('.navspy');
        $navspy.hide();

        this.$el.find('.o_portal_contact_details').parent().hide();
        this.$el.find('#portal_connect_software_modal_btn').parent().hide();
        const $odooFooter = this.$el.find('a[href*="odoo.com"]').closest('div');
        $odooFooter.removeClass('d-lg-block d-block').hide();
    },
});
