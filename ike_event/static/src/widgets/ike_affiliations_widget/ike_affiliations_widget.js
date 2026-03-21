import { Component, useEffect, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Field } from "@web/views/fields/field";


export class IkeAffiliations extends Component {
    static template = "ike_event.IkeAffiliations";

    static components = { Field };

    static props = {
        ...standardWidgetProps,
        button_label: { type: String, optional: true },
        user_field: { type: String, optional: true },
        phone_field: { type: String, optional: true },
        additional_phone_field: { type: String, optional: true },
        subscription_field: { type: String, optional: true },
    };

    static defaultProps = {
        button_label: _t("See detail")
    };

    setup() {
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.action = useService("action");
        this.busService = this.env.services.bus_service;
        this.state = useState({
            loading: false,
            userId: null,  // Id del usuario, se actualiza conforme cambia el campo de usuario proporcionado en los props
            userInfo: null,  // Información del usuario, se actualiza conforme cambia el userId
            userPhone: "",  // Teléfono del usuario, se actualiza conforme cambia el campo de teléfono proporcionado en los props
            userAdditionalPhone: "",  // Teléfono adicional del usuario, se actualiza conforme cambia el campo de teléfono adicional proporcionado en los props
            currentAffiliationId: null,  // Afiliación actual del usuario, se actualiza conforme cambia el valor del campo de afiliación proporcionado en los props
            currentAffiliationInfo: null,
            userAffiliationsActive: [],  // Afiliaciones activas del usuario, se actualiza conforme cambia el valor de userId, obtenemos las afiliaciones activas
            userAffiliationsInactive: [],  // Afiliaciones inactivas del usuario, se actualiza conforme cambia el valor de userId, obtenemos las afiliaciones inactivas
        });

        const userFieldName = this.props.user_field;
        try {
            this.validateUserField(userFieldName);
            this.userFieldName = userFieldName;
        } catch (error) {
            this.notification.add(error.message, {
                type: "danger",
                title: _t("Widget configuration error"),
            });
            this.userFieldName = null;
        }

        // Detectamos el cambio del usuario en la vista para actualizar datos
        useEffect((userId) => {
            if (userId) {
                this._loadUserData(userId);
            } else {
                this.state.userId = null;
                this.state.userInfo = null;
                this.state.userAffiliationsActive = [];
                this.state.userAffiliationsInactive = [];
            }
        }, () => [this.userId]);

        // El usuario tiene un teléfono, se podría tomar de allí, pero dado que no estamos 100% seguros que siempre llamen de allí
        // o que siempre sea el usuario quien marque, tomamos el de la vista, el adicional siempre debe actualizase por el que proporcionen en la vista
        useEffect((userPhone, userAdditionalPhone) => {
            this.state.userPhone = userPhone ? this.formatPhone(userPhone) : "";
            this.state.userAdditionalPhone = userAdditionalPhone ? this.formatPhone(userAdditionalPhone) : "";
        }, () => [this.userPhone, this.userAdditionalPhone]);

        // Affiliations
        useEffect((currentAffiliationId) => {
            this._updateCurrentAffiliationInfo(currentAffiliationId);
        }, () => [this.currentAffiliationId]);

        useEffect((membership_validity) => {
            const currentAffiliationId = this.state.currentAffiliationId;
            if (currentAffiliationId !== null) {
                this._updateCurrentAffiliationInfo(currentAffiliationId);
            }
        }, () => [this.props.record?.data.membership_validity]);

        onWillStart(async () => {
            this.subscribeToChannel();
        });

        onWillUnmount(() => {
            this.unsubscribeFromChannel();
        });
        console.log(this);
    }

    subscribeToChannel() {
        const eventId = this.props.record.resId;
        this.busChannel = `ike_channel_event_${eventId}`;
        this.busService.addChannel(this.busChannel);
        this.busService.subscribe("ike_event_membership_info_reload", this.handleNotification );
        console.log("Subscribed to channel", this.busChannel);
    }

    unsubscribeFromChannel() {
        if (this.busChannel) {
            this.busService.deleteChannel(this.busChannel);
            this.busService.unsubscribe("ike_event_membership_info_reload", this.handleNotification );
        }
    }

    handleNotification  = async (message) => {
        // Recargar datos de la afiliación actual
        const currentAffiliationId = this.state.currentAffiliationId;
        if (currentAffiliationId !== null) {
            this._updateCurrentAffiliationInfo(currentAffiliationId);
        }
    }

    formatPhone(phone) {
        let digits = phone.replace(/\D/g, "").replace(" ", "");
        if (digits.length == 10) {
            return digits.replace(/(\d{2})(\d{4})(\d{4})/, '($1) $2 $3');
        } else if (digits.length == 12 && digits.startsWith('52')) {
            return digits.replace(/52(\d{2})(\d{4})(\d{4})/, '+52 ($1) $2 $3');
        } else {
            return phone;
        }
    }

    async _loadUserData(userId) {
        const expectedUserId = userId;
        this.state.userId = userId;
        this.state.loading = true;
        try {
            const [users, affiliations] = await Promise.all([
                // RPC 1: info del usuario
                this.orm.searchRead("custom.nus", [["id", "=", userId]],
                    ["id", "display_name", "email", "phone", "vip_user"]),
                // RPC 2: afiliaciones del usuario
                this.orm.searchRead("custom.membership.nus", [["nus_id", "=", userId]],
                    [
                        'id', 'name', 'key_identification', 'x_validation_pattern', 'x_display_mask',
                        'subscription_validity', 'vehicle_weight_category_id', 'check_is_special'
                    ],
                    { order: 'id asc' })
            ]);

            if (this.state.userId !== expectedUserId) return;

            // Usuario
            if (users.length > 0) {
                this.state.userInfo = {
                    id: users[0].id,
                    name: users[0].display_name,
                    email: users[0].email,
                    phone: users[0].phone,
                    vip: users[0].vip_user,
                };
            } else {
                this.state.userInfo = null;
            }

            // Afiliaciones
            this.state.userAffiliationsActive = affiliations.filter(x => x.subscription_validity);
            this.state.userAffiliationsInactive = affiliations.filter(x => !x.subscription_validity);

        } catch (error) {
            console.error("Error cargando datos del usuario:", error);
            this.notification.add("Error al cargar información del usuario", {
                type: "danger"
            });
        } finally {
            if (this.state.userId === expectedUserId) {
                this.state.loading = false;
            }
        }
    }

    get isSpecial() {
        return this.props.record.data['check_is_special'] || false;
    }

    get userId() {
        const userValue = this.props.record.data[this.userFieldName];
        return Array.isArray(userValue) ? userValue[0] : userValue || null;
    }

    get userPhone() {
        const userPhoneValue = this.props.record.data[this.props.phone_field];
        return Array.isArray(userPhoneValue) ? userPhoneValue[0] : userPhoneValue || null;
    }

    get userAdditionalPhone() {
        const userAdditionalPhoneValue = this.props.record.data[this.props.additional_phone_field];
        return Array.isArray(userAdditionalPhoneValue) ? userAdditionalPhoneValue[0] : userAdditionalPhoneValue || null;
    }

    get currentAffiliationId() {
        const subscriptionFieldValue = this.props.record.data[this.props.subscription_field];
        return Array.isArray(subscriptionFieldValue) ? subscriptionFieldValue[0] : subscriptionFieldValue || null;
    }

    validateUserField(fieldName) {
        if (!fieldName) return;
        const fields = this.props.record.fields;
        if (!fields[fieldName]) {
            throw new Error(
                _t(`The field '${fieldName}' does not exist in the model '${this.props.record.resModel}'`)
            );
        }
        const field = fields[fieldName];
        if (field.type !== 'many2one') {
            throw new Error(
                _t(`Field '${fieldName}' must be of type 'many2one' (current: '${field.type}')`)
            );
        }
        if (field.relation !== 'custom.nus') {
            throw new Error(
                _t(`The field '${fieldName}' must be related to 'custom.nus' (current: '${field.relation}')`)
            );
        }
        return true;
    }

    openAffiliationDetails = () => {
        this.action.doAction({
            res_model: 'custom.membership.nus',
            name: _t('Affiliations'),
            type: 'ir.actions.act_window',
            views: [[false, 'kanban']],
            target: 'new',
            domain: [['nus_id', '=', this.state.userId], ['disabled', '=', false]],
            context: {hide_disabled_enabled_filters: 1}
        });
    }

    openCoverageDetails = () => {
        //obtenemos el membershiop del actual
        const membershipPlanId = this.state.currentAffiliationInfo?.membership_plan_id?.[0];
        const vehicleMembershipWeigth = this.state.currentAffiliationInfo?.vehicle_weight_category_id?.[0];
        if (!membershipPlanId) {
            this.notification.add("No se encontró el plan de membresía", {
                type: "warning"
            });
            return;
        }
        //ejecuta la accion del modelo
        this.action.doAction({
            res_model: 'custom.membership.plan.product.line',
            name: _t('Coverage Details'),
            type: 'ir.actions.act_window',
            views: [[false, 'kanban']],
            target: 'new',
            context: {group_by: ['service_id']},
            domain: [
                ['membership_plan_id', '=', membershipPlanId],
                '|',
                ['vehicle_weight_category_id', '=', vehicleMembershipWeigth],
                ['vehicle_weight_category_id', '=', false],
            ],
        });
    }

    async _updateCurrentAffiliationInfo(currentAffiliationId) {
        const expectedAffId = currentAffiliationId;
        this.state.currentAffiliationId = currentAffiliationId;
        if (currentAffiliationId) {
            try {
                const records = await this.orm.searchRead('custom.membership.nus', [
                    ['id', '=', currentAffiliationId],
                    ['subscription_validity', '=', true]
                ], ['id', 'name', 'membership_plan_id', 'key_identification', 'x_validation_pattern', 'x_display_mask', 'subscription_validity', 'vehicle_weight_category_id', 'check_is_special'], { order: 'id asc', limit: 1 });

                if (this.state.currentAffiliationId !== expectedAffId) return;

                if (records.length > 0) {
                    this.state.currentAffiliationInfo = records[0];
                } else {
                    this.state.currentAffiliationInfo = null;
                }
            } catch (error) {
                console.error("Error cargando afiliación actual:", error);
            }
        } else {
            this.state.currentAffiliationInfo = null;
        }
    }

    getFieldLabel(fieldName) {
        return this.props.record.fields[fieldName]?.string || fieldName;
    }

    get buttonText() {
        return this.props.button_label;
    }
}

export const ikeAffiliations = {
    component: IkeAffiliations,
    extractProps(fieldInfo, dynamicInfo) {
        return {
            button_label: fieldInfo.attrs.button_label,
            user_field: fieldInfo.attrs.user_field,
            phone_field: fieldInfo.attrs.phone_field,
            additional_phone_field: fieldInfo.attrs.additional_phone_field,
            subscription_field: fieldInfo.attrs.subscription_field,
        };
    },
};

registry.category("view_widgets").add("ike_affiliations", ikeAffiliations);
