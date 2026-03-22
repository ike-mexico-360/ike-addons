import { _t } from '@web/core/l10n/translation';
import { patch } from '@web/core/utils/patch';
import { useService } from '@web/core/utils/hooks';
import { useState } from '@odoo/owl';
import { utils } from '@web/core/ui/ui_service';

import { CheckBox } from '@web/core/checkbox/checkbox';
import { ControlPanel } from '@web/search/control_panel/control_panel';

import { useUdooStore, useUdooLocalStore } from '@omux_state_manager/store';


patch(ControlPanel.prototype, {

    setup() {
        super.setup();

        if (this.env.services['mail.store']) {
            this.store = useState(useService('mail.store'));
        }
        this.ui = useService('ui');
        this.ue = useUdooLocalStore();
        this.uo = useUdooStore();

        this.store.uQuickRepeat = false;
    },

    uInitLayter() {
        this.store.focusChatter = document.querySelectorAll('.o-mail-Form-chatter.o-aside').length > 0;
        this.hasAttachmentPreview = document.querySelectorAll('div.o_attachment_preview').length > 0;
        this.hasChatter = document.querySelectorAll('.o-mail-Form-chatter').length > 0;
        this.hasList = document.querySelectorAll('.o_list_table').length > 0;
    },

    uSwitchAside(dir) {
        this.env.bus.trigger('CHR:SWITCH', dir);
        if (dir == 'b') {
            if (utils.getPureSize() > 4) {
                odoo.sett_uisize = 4;
                this.ui.size = odoo.sett_uisize;
                this.ue.sett_uisize = odoo.sett_uisize;
                document.body.classList.add('uup');
            } else {
                delete odoo.sett_uisize;
                delete this.ue.sett_uisize;
            }
        } else if (dir == 'r') {
            if (utils.getPureSize() > 4) {
                delete odoo.sett_uisize;
                delete this.ue.sett_uisize;
            }
        }
        window.dispatchEvent(new Event('resize'));
    },

    uReloadLayout() {
        this.env.bus.trigger('LYT:RESET');
    },

    uSwitchPopMode() {
        this.ui.dropinMode = !this.ui.dropinMode;
        this.state.dropinMode = this.ui.dropinMode;

        // Hide layter dropdown to renew ui state
        setTimeout(() => {
            this.root.el.querySelector('.u_layter_tg').click();
        }, 140);
    },

    uBookmarkThis() {
        this.env.bus.trigger('UDOO:BMK');
    },

    uBackTrick() {
        const backBtn = document.querySelector('.breadcrumb-item.o_back_button');
        if (backBtn) {
            backBtn.click();
        } else {
            this.actionService.restore();
        }
    },

    uQuickRepeatCheck(checked) {
        this.store.uQuickRepeat = checked;
        if (checked) {
        }
    },
});

ControlPanel.components = {
    ...ControlPanel.components,
    CheckBox,
}