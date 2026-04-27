
import { Component, onWillStart, useState, } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { UserCreateComponent } from "./user_create_component";
import { UserReadComponent } from "./user_read_component";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";
import { usePagination } from "../pagination/pagination_service";
import { PaginationComponent } from "../pagination/pagination_component";

export class UsersMainComponent extends Component {
    static template = "ike_event_portal.UsersMainComponent";
    static components = { UserCreateComponent, UserReadComponent, PaginationComponent };
    setup() {
        this.orm = useService("orm");
        this.user = user;
        this.supplier_id = 0;
        this.state = useState({
            users: [],
            isLoading: true,
            selectedUserId: null,
            view: 'list', // 'list', 'detail', or 'create',
            notification: null
        });
        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.state.users
        });
        onWillStart(async () => {
            await this.getSupplierId();
            await this.loadUsers();
            await this.checkIfAdmin();
        });
    }

    async loadUsers() {
        this.state.isLoading = true;
        this.state.error = null;
        try {
            const drivers = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [],
                ['user_id', 'supplier_id', 'center_of_attention_id', 'user_type'],
            );
            const drivers_filtered = drivers.filter(x => x.supplier_id && x.supplier_id[0] === this.supplier_id);
            const user_ids = drivers_filtered.map(x => x.user_id ? x.user_id[0] : null).filter(Boolean);
            
            // Create a map of user_id -> driver data for quick lookup
            const driverMap = {};
            drivers_filtered.forEach(d => {
                if (d.user_id) {
                    driverMap[d.user_id[0]] = d;
                }
            });
            
            const users = await rpc('/provider/portal/users/search', {
                domain: [['id', 'in', user_ids]],
                fields: ['id', 'name', 'email']
            });
            
            // Attach center_of_attention and user_type to each user
            this.state.users = users.map(user => {
                const driverData = driverMap[user.id] || {};
                return {
                    ...user,
                    center_of_attention_name: driverData.center_of_attention_id ? driverData.center_of_attention_id[1] : '',
                    user_type: driverData.user_type || '',
                };
            });
        } catch (err) {
            console.error("Error loading users:", err);
            this.state.error = "Failed to load users. Please try again.";
        } finally {
            this.state.isLoading = false;
        }
    }

    // Method to show the form
    openCreateForm() {
        this.state.isCreating = true;
        this.state.view = 'create';
    }

    // Method to hide the form (passed to child as prop)
    closeCreateForm() {
        this.state.isCreating = false;
        this.state.view = 'list';
    }

    // Method called when user is successfully created
    onUserCreated() {
        this.state.isCreating = false;
        this.state.view = 'list';
        this.loadUsers(); // Refresh the user list after creation
    }

    // 5. Method to clear selection (Back to List Mode)
    clearSelection() {
        this.state.selectedUserId = null;
    }

    selectUser(userId) {
        this.state.selectedUserId = userId;
        this.state.isCreating = false;
    }

    async getSupplierId() {
        try {
            let supplier_drivers = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [],
                []
            );
            let supplier = supplier_drivers.find(x => x.user_id && x.user_id[0] === this.user.userId);
            if(!supplier) {
                this.state.notification = { type: 'warning', message: 'El usuario no está asociado a ningún proveedor.' };
                return;
            }
            this.supplier_id = supplier.supplier_id[0];
        }
        catch (e) {
            this.state.notification = { type: 'error', message: 'Error al obtener el proveedor asociado.' };
        }

    }

    closeNotification() {
        this.state.notification = null;
    }

    async checkIfAdmin() {
        const result = await rpc('/provider/portal/user/check_admin', {});

        if (result) {
            console.log("User is an admin");
            // Show admin features
        } else {
            console.log("User is not an admin");
            // Hide admin features
        }
    }
}


registry.category("public_components").add("ike_event_portal.UsersMainComponent", UsersMainComponent);