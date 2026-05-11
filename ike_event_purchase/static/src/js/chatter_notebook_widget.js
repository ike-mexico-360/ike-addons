/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, xml } from "@odoo/owl";
import { Chatter } from "@mail/chatter/web_portal/chatter";

export class NotebookChatter extends Component {
    static template = xml`
        <div class="o_notebook_chatter">
            <Chatter
                threadModel="props.record.resModel"
                threadId="props.record.resId"
            />
        </div>
    `;
    static components = { Chatter };
}

// En Odoo 18, los widgets de campo deben registrarse con una estructura específica
export const notebookChatterField = {
    component: NotebookChatter,
    supportedTypes: ["one2many", "many2many"],
};

registry.category("fields").add("notebook_chatter", notebookChatterField);