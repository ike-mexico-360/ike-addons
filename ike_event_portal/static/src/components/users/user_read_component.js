/** @odoo-module **/

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";

export class UserReadComponent extends Component {
    static template = "ike_event_portal.UserReadComponent";
    static props = {
        userId: { type: Number, optional: true },
        onClose: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            user: null,
            isLoading: false,
            error: null,
        });

        onWillStart(async () => {
            if (this.props.userId) {
                await this.loadUser(this.props.userId);
            }
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps.userId && nextProps.userId !== this.props.userId) {
                await this.loadUser(nextProps.userId);
            }
        });
    }

    async loadUser(id) {
        this.state.isLoading = true;
        this.state.error = null;
        try {
            const [userData] = await rpc('/provider/portal/users/search', {
                domain: [['id', '=', id]],
                fields: [
                    'name', 'login', 'email', 'phone',
                    'street', 'street2', 'zip', 'city', 'country_id', 'state_id',
                    'partner_id', 'groups_id'
                ]
            });

            this.state.user = userData;
            this.state.user.center_of_attention_name = await this.getCenterAttentionName(id);

            // 2. Fetch Partner VAT (License) if partner exists
            if (userData && userData.partner_id) {
                const [partnerData] = await this.orm.read('res.partner', [userData.partner_id[0]], ['vat']);
                this.state.partner_vat = partnerData.vat;
            }
        } catch (error) {
            console.error("Error loading user:", error);
            this.state.error = "Failed to load user details.";
        } finally {
            this.state.isLoading = false;
        }
    }

    async getCenterAttentionName(user_id) {
        try {
            let supplier_driver = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [['user_id', 'in', [user_id]]],
                []
            );
            if(supplier_driver.length > 0) {
                let center_name = supplier_driver[0].center_of_attention_id[1];
                return center_name;
            }
        } catch (error) {
            console.error("Error fetching center of attention name:", error);
            return "Unknown Center";
        }
    }

}

registry.category("public_components").add("ike_event_portal.UserReadComponent", UserReadComponent);