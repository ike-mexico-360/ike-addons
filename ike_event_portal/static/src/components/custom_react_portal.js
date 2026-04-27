import { Component, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { useServices } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class CustomReactApp extends Component {
    static template = "ike_event_portal.CustomReactApp";

    setup() {
        console.log("CustomReactApp setup called");
        this.root = useRef("root"); // Reference to the div in the template
        this.reactRoot = null; // To store the React root instance

        onMounted(() => {
            console.log("CustomReactApp mounted");
            // When the Owl component is mounted, mount the React app
            if (window.mountReactApp) {
                console.log("Mounting React app");
                this.reactRoot = window.mountReactApp(this.root.el);
            }
        });

        onWillUnmount(() => {
            console.log("CustomReactApp will unmount");
            // When the Owl component is about to be destroyed, unmount the React app
            if (window.unmountReactApp) {
                window.unmountReactApp(this.reactRoot);
            }
        });
    }
}

registry.category("public_components").add("ike_event_portal.CustomReactApp", CustomReactApp);
