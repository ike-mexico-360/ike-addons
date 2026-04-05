import { registry } from "@web/core/registry";
import { Layout } from "@web/search/layout";
import { View } from "@web/views/view";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

import { Component, onWillStart, onWillUnmount, useState, useSubEnv } from '@odoo/owl';


class IkeDashboardEvent extends Component {
    static components = { Layout, View };
    static template = "ike_event.IkeDashboardEvent";
    static props = {
        ...standardActionServiceProps,
    };
    setup() {
        console.log("IkeDashboardEvent", this);
        this.display = {
            controlPanel: {},
        };

        useSubEnv({
            ...this.env,
            config: {
                ...this.env.config,
            },
        });

        this.orm = this.env.services.orm;
        this.busService = this.env.services.bus_service;

        this.state = useState({
            events: [],
        })

        onWillStart(async () => {
            const result = await this.env.services.orm.webSearchRead(
                "ike.event", [['stage_ref', '=', 'searching']], {
                specification: {
                    id: {},
                    name: {},
                    stage_ref: {},
                    service_supplier_ids: {
                        fields: {
                            id: {},
                            supplier_id: {
                                fields: {
                                    id: {},
                                    name: {},
                                },
                            },
                            state: {},
                            assignation_type: {},
                            notification_date: {},
                        }
                    }
                },
            });
            console.log(result)
            if (result.records) {
                this.state.events = result.records;
            }
        });

        onWillUnmount(() => {

        });
    }
}

registry.category("lazy_components").add("IkeDashboardEvent", IkeDashboardEvent);
