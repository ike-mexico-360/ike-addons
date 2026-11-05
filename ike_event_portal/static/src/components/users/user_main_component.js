
import { Component, onWillStart, useExternalListener, useState, } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";
import { UserCreateComponent } from "./user_create_component";
import { UserReadComponent } from "./user_read_component";
import { UserPasswordDialog } from "./user_password_dialog";
import { user } from "@web/core/user";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { usePagination } from "../pagination/pagination_service";
import { PaginationComponent } from "../pagination/pagination_component";

// Name and row actions are mandatory and therefore absent here.
const OPTIONAL_USER_COLUMNS = [
    { key: "email", label: _t("Email") },
    { key: "center", label: _t("Attention center") },
    { key: "user_type", label: _t("Type") },
    { key: "last_change", label: _t("Last change") },
];
// Browser-only preference: the column choice is a per-viewer convenience.
const COLUMNS_STORAGE_KEY = "ike_event_portal.users.visible_columns";

// One stat card per user type, in the order they are shown.
const USER_TYPE_CARDS = [
    { type: "administrator", color: "#dc3545" },
    { type: "supervisor", color: "#fd7e14" },
    { type: "financial", color: "#212529" },
    { type: "operator", color: "#0d6efd" },
];

export class UsersMainComponent extends Component {
    static template = "ike_event_portal.UsersMainComponent";
    static components = { UserCreateComponent, UserReadComponent, PaginationComponent };
    setup() {
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        this.notification = useService("notification");
        this.user = user;
        this.supplier_id = 0;
        this.state = useState({
            users: [],
            isLoading: true,
            isAdmin: false,
            selectedUserId: null,
            view: 'list', // 'list', 'detail', or 'create',
            notification: null,
            userTypeLabels: {},
            filters: {
                name: "",
                email: "",
                center_id: "",
                user_type: "",
            },
            sort: { column: 'name', direction: 'asc' },
            visibleColumns: this.loadColumnPreferences(),
            columnMenuOpen: false,
            actionsMenuUserId: null,
            updatingUserId: null,
            header: {
                supplierName: "",
                supplierRfc: "",
                centers: [],
                selectedCenterId: null,
                centerMenuOpen: false,
                userName: "",
                userEmail: "",
                userRole: "",
            },
        });
        this.pagination = usePagination({
            pageSize: 10,
            getItems: () => this.filteredUsers
        });

        // Close the open menus when clicking anywhere else.
        useExternalListener(window, "click", () => {
            this.state.actionsMenuUserId = null;
            this.state.columnMenuOpen = false;
            this.state.header.centerMenuOpen = false;
        });

        onWillStart(async () => {
            await this.getSupplierId();
            await Promise.all([
                this.loadUsers(),
                this.loadHeaderInfo(),
                this.checkIfAdmin(),
            ]);
        });
    }

    async loadUsers() {
        this.state.isLoading = true;
        this.state.error = null;
        try {
            const [drivers, fieldsData] = await Promise.all([
                // Only the relations of the current user's supplier.
                this.orm.searchRead(
                    'res.partner.supplier_users.rel',
                    [['supplier_id', '=', this.supplier_id]],
                    ['user_id', 'supplier_id', 'center_of_attention_id', 'user_type'],
                ),
                this.orm.call('res.partner.supplier_users.rel', 'fields_get', [['user_type']], {
                    attributes: ['selection'],
                }),
            ]);
            // Labels translated through the module's i18n files.
            this.state.userTypeLabels = Object.fromEntries(
                (fieldsData.user_type?.selection || []).map(([value, label]) => [value, _t(label)])
            );

            const user_ids = drivers.map(x => x.user_id ? x.user_id[0] : null).filter(Boolean);

            // Create a map of user_id -> driver data for quick lookup
            const driverMap = {};
            drivers.forEach(d => {
                if (d.user_id) {
                    driverMap[d.user_id[0]] = d;
                }
            });

            const [users, lastChanges] = await Promise.all([
                rpc('/provider/portal/users/search', {
                    domain: [['id', 'in', user_ids]],
                    fields: ['id', 'name', 'email', 'login', 'active']
                }),
                this.loadLastChanges(user_ids),
            ]);

            // Attach center_of_attention, user_type and last change to each user
            this.state.users = users.map(user => {
                const driverData = driverMap[user.id] || {};
                const lastChange = lastChanges[user.id];
                return {
                    ...user,
                    center_of_attention_id: driverData.center_of_attention_id ? driverData.center_of_attention_id[0] : null,
                    center_of_attention_name: driverData.center_of_attention_id ? driverData.center_of_attention_id[1] : '',
                    user_type: driverData.user_type || '',
                    last_change_raw: lastChange ? lastChange.date : "",
                    last_change_date: lastChange ? formatDateTime(deserializeDateTime(lastChange.date)) : "",
                    last_change_user: lastChange ? (lastChange.is_system ? _t("System") : lastChange.user) : "",
                };
            });
        } catch (err) {
            console.error("Error loading users:", err);
            this.state.error = "Failed to load users. Please try again.";
        } finally {
            this.state.isLoading = false;
        }
    }

    async loadLastChanges(userIds) {
        try {
            const result = await rpc('/provider/portal/users/last_changes', { user_ids: userIds });
            return (result && result.success && result.changes) || {};
        } catch (error) {
            // The column is informational: the list still loads without it.
            console.warn("Unable to load users last changes:", error);
            return {};
        }
    }

    // ---------------------------------------------------------------- Header

    async loadHeaderInfo() {
        try {
            const header = this.state.header;

            const [[userData], roleLabel] = await Promise.all([
                this.orm.searchRead('res.users', [['id', '=', this.user.userId]], ['name', 'email']),
                this.getUserRoleLabel(),
            ]);
            // this.user.name can come back empty on website/portal pages, hence the ORM read.
            header.userName = (userData && userData.name) || this.user.name || "";
            header.userEmail = (userData && userData.email) || "";
            header.userRole = roleLabel;

            if (!this.supplier_id) return;

            const [supplier] = await this.orm.searchRead(
                'res.partner',
                [['id', '=', this.supplier_id]],
                ['name', 'vat', 'x_supplier_center_ids']
            );
            if (!supplier) return;

            header.supplierName = supplier.name || "";
            header.supplierRfc = supplier.vat || "";

            if (supplier.x_supplier_center_ids && supplier.x_supplier_center_ids.length) {
                header.centers = await this.orm.searchRead(
                    'res.partner',
                    [['id', 'in', supplier.x_supplier_center_ids]],
                    ['name']
                );
            }
        } catch (err) {
            // Non-blocking: the header is informational, the page still works without it.
            console.warn("Error loading header info:", err);
        }
    }

    async getUserRoleLabel() {
        const roleGroups = [
            ['ike_event_portal.custom_group_portal_admin', _t("Supplier Administrator")],
            ['ike_event_portal.custom_group_portal_supervisor', _t("Supplier Supervisor")],
            ['ike_event_portal.custom_group_portal_finance', _t("Supplier Finance")],
            ['ike_event_portal.custom_group_portal_operator', _t("Supplier Operator")],
        ];
        for (const [group, label] of roleGroups) {
            if (await user.hasGroup(group)) {
                return label;
            }
        }
        return _t("Supplier User");
    }

    get selectedCenterName() {
        if (!this.state.header.selectedCenterId) return _t("All Centers");
        const center = this.state.header.centers.find(c => c.id === this.state.header.selectedCenterId);
        return center ? center.name : "";
    }

    get userInitials() {
        // First letter of the first and last words of the name.
        const parts = this.state.header.userName.trim().split(/\s+/).filter(Boolean);
        if (!parts.length) return "";
        if (parts.length === 1) return parts[0][0].toUpperCase();
        return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }

    logout() {
        window.location.href = "/web/session/logout?redirect=/";
    }

    toggleCenterMenu() {
        this.state.header.centerMenuOpen = !this.state.header.centerMenuOpen;
    }

    selectCenter(centerId) {
        this.state.header.selectedCenterId = centerId;
        this.state.header.centerMenuOpen = false;
        this.pagination.reset();
    }

    // ---------------------------------------------------------------- Columns

    loadColumnPreferences() {
        const allColumns = OPTIONAL_USER_COLUMNS.map((column) => column.key);
        try {
            const saved = JSON.parse(window.localStorage.getItem(COLUMNS_STORAGE_KEY));
            if (Array.isArray(saved)) {
                return allColumns.filter((column) => saved.includes(column));
            }
        } catch {
            // Storage unavailable or corrupted: show every column.
        }
        return allColumns;
    }

    get optionalUserColumns() {
        return OPTIONAL_USER_COLUMNS;
    }

    isColumnVisible(column) {
        return this.state.visibleColumns.includes(column);
    }

    get userColumnCount() {
        // Mandatory name column, selected optional columns, and actions.
        return this.state.visibleColumns.length + 2;
    }

    toggleColumnMenu() {
        this.state.columnMenuOpen = !this.state.columnMenuOpen;
    }

    toggleColumn(column, checked) {
        const columns = checked
            ? [...this.state.visibleColumns, column]
            : this.state.visibleColumns.filter((visibleColumn) => visibleColumn !== column);
        this.state.visibleColumns = OPTIONAL_USER_COLUMNS
            .map((optionalColumn) => optionalColumn.key)
            .filter((key) => columns.includes(key));
        try {
            window.localStorage.setItem(COLUMNS_STORAGE_KEY, JSON.stringify(this.state.visibleColumns));
        } catch {
            // Not persisted, but still applied for this visit.
        }
    }

    // ---------------------------------------------------------------- Filters, stats and sorting

    get filteredUsers() {
        return this.sortUsers(this.state.users.filter(user => this.matchesFilters(user)));
    }

    // Centro de atención (header and filter), name, email and user type filters.
    matchesFilters(user) {
        const { filters, header } = this.state;
        const normalize = (value) => (value || "").toString().toLowerCase();

        if (header.selectedCenterId && user.center_of_attention_id !== header.selectedCenterId) {
            return false;
        }
        if (filters.center_id && user.center_of_attention_id !== parseInt(filters.center_id, 10)) {
            return false;
        }
        const name = normalize(filters.name).trim();
        if (name && !normalize(user.name).includes(name)) {
            return false;
        }
        const email = normalize(filters.email).trim();
        if (email && !normalize(user.email || user.login).includes(email)) {
            return false;
        }
        return !filters.user_type || user.user_type === filters.user_type;
    }

    get userStats() {
        // The cards reflect every active filter, including the selected user type.
        const users = this.state.users.filter(user => this.matchesFilters(user));
        const stats = { total: users.length };
        for (const { type } of USER_TYPE_CARDS) {
            stats[type] = users.filter(user => user.user_type === type).length;
        }
        return stats;
    }

    get userTypeCards() {
        return USER_TYPE_CARDS.map(card => ({
            ...card,
            label: this.userTypeLabel(card.type),
            count: this.userStats[card.type],
        }));
    }

    userTypeLabel(userType) {
        return this.state.userTypeLabels[userType] || userType || "";
    }

    userTypeBadgeClass(userType) {
        return {
            administrator: "bg-danger-subtle text-danger",
            supervisor: "bg-warning-subtle text-warning-emphasis",
            financial: "bg-secondary-subtle text-dark",
            operator: "bg-primary-subtle text-primary",
        }[userType] || "bg-secondary-subtle text-secondary";
    }

    // Clicking a card filters by its type; clicking it again (or Total) clears it.
    selectUserType(userType) {
        this.updateFilter('user_type', this.state.filters.user_type === userType ? "" : userType);
    }

    updateFilter(field, value) {
        this.state.filters[field] = value;
        this.pagination.reset();
    }

    clearFilters() {
        Object.assign(this.state.filters, { name: "", email: "", center_id: "", user_type: "" });
        this.pagination.reset();
    }

    // Value used to sort each column, as shown in the table.
    sortValue(user, column) {
        switch (column) {
            case 'name': return user.name || "";
            case 'email': return user.email || user.login || "";
            case 'center': return user.center_of_attention_name || "";
            case 'user_type': return this.userTypeLabel(user.user_type);
            case 'last_change': return user.last_change_raw || "";
            default: return "";
        }
    }

    sortUsers(users) {
        const { column, direction } = this.state.sort;
        const factor = direction === 'asc' ? 1 : -1;
        return [...users].sort((a, b) => {
            const valueA = this.sortValue(a, column);
            const valueB = this.sortValue(b, column);
            // Empty values always go last, whatever the direction.
            if (!valueA || !valueB) {
                return !valueA - !valueB;
            }
            return factor * String(valueA).localeCompare(String(valueB), undefined, { numeric: true, sensitivity: 'base' });
        });
    }

    toggleSort(column) {
        const sort = this.state.sort;
        if (sort.column === column) {
            sort.direction = sort.direction === 'asc' ? 'desc' : 'asc';
        } else {
            sort.column = column;
            sort.direction = 'asc';
        }
        this.pagination.reset();
    }

    sortIcon(column) {
        const { column: current, direction } = this.state.sort;
        if (current !== column) {
            return 'fa fa-sort text-muted';
        }
        return direction === 'asc' ? 'fa fa-sort-asc' : 'fa fa-sort-desc';
    }

    // Exports every user matching the current filters (all pages), in the current sort order.
    downloadExcel() {
        const ids = this.filteredUsers.map(user => user.id).join(',');
        window.open(`/provider/portal/users/download/xlsx?ids=${ids}`, '_blank');
    }

    // ---------------------------------------------------------------- Row actions

    toggleActionsMenu(userId) {
        this.state.actionsMenuUserId = this.state.actionsMenuUserId === userId ? null : userId;
    }

    isCurrentUser(userRecord) {
        return userRecord.id === this.user.userId;
    }

    onEditClick(userRecord) {
        this.state.actionsMenuUserId = null;
        this.selectUser(userRecord.id);
    }

    onResetPasswordClick(userRecord) {
        this.state.actionsMenuUserId = null;
        this.dialog.add(UserPasswordDialog, {
            userId: userRecord.id,
            userName: userRecord.name,
            onPasswordChanged: () => this.showNotification({
                message: _t("The password was changed."),
                type: 'success',
                sticky: false,
            }),
        });
    }

    onToggleActiveClick(userRecord) {
        this.state.actionsMenuUserId = null;
        if (this.isCurrentUser(userRecord)) {
            return;
        }
        const activate = !userRecord.active;
        this.dialog.add(ConfirmationDialog, {
            title: activate ? _t("Activate user") : _t("Deactivate user"),
            body: activate
                ? _t("%s will be able to log in to the portal again.", userRecord.name)
                : _t("%s will no longer be able to log in to the portal.", userRecord.name),
            confirmLabel: activate ? _t("Activate") : _t("Deactivate"),
            confirm: () => this.setUserActive(userRecord, activate),
            cancel: () => {},
        });
    }

    async setUserActive(userRecord, active) {
        this.state.updatingUserId = userRecord.id;
        try {
            const result = await rpc('/provider/portal/user/set_active', { user_id: userRecord.id, active });
            if (!result || !result.success) {
                throw new Error((result && result.error) || _t("The user status could not be changed."));
            }
            await this.loadUsers();
        } catch (error) {
            this.showNotification({ title: _t("Error"), message: error.message, type: 'danger' });
        } finally {
            this.state.updatingUserId = null;
        }
    }

    showNotification({ message, type = 'info', sticky = true, title }) {
        this.notification.add(message, { type, sticky, title });
    }

    // ---------------------------------------------------------------- Views

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
            // Only the current user's relation, and only the field needed.
            const [supplier] = await this.orm.searchRead(
                'res.partner.supplier_users.rel',
                [['user_id', '=', this.user.userId]],
                ['supplier_id'],
                { limit: 1 }
            );
            if (!supplier || !supplier.supplier_id) {
                this.state.notification = { type: 'warning', message: 'The user is not associated with any supplier.' };
                return;
            }
            this.supplier_id = supplier.supplier_id[0];
        }
        catch (e) {
            this.state.notification = { type: 'error', message: 'Error occurred while fetching the associated supplier.' };
        }

    }

    closeNotification() {
        this.state.notification = null;
    }

    async checkIfAdmin() {
        try {
            this.state.isAdmin = (await rpc('/provider/portal/user/check_admin', {})) === true;
        } catch {
            this.state.isAdmin = false;
        }
    }
}


registry.category("public_components").add("ike_event_portal.UsersMainComponent", UsersMainComponent);
