/** @odoo-module **/

import { Component, useState, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class IkeLineProgress extends Component {
    static template = "ike_event.IkeLineProgress";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({ now: Date.now() });

        this.timer = setInterval(() => {
            if (this.isActiveRoute) {
                this.state.now = Date.now();
            }
        }, 1000);

        onWillUnmount(() => clearInterval(this.timer));
    }
    /* ======================
     * ESTADO ACTUAL
     * ====================== */
    get stage() {
        return this.props.record.data.stage_ref || "";
    }

    get isRouteToUser() {
        return this.stage === "on_route";
    }

    get isRouteToDestination() {
        return this.stage === "on_route_2";
    }

    get isArrived() {
        return this.stage === "arrived";
    }

    get isArrived2() {
        return this.stage === "arrived_2";
    }

    get isActiveRoute() {
        return this.isRouteToUser || this.isRouteToDestination;
    }
    /* ======================
     * DURACIONES
     * ====================== */
    get routeToUserDuration() {
        const minutes = this.props.record.data.estimated_duration || 0;
        return Math.max(Math.round(minutes * 60), 1);
    }

    get routeToOriginDuration() {
        const minutes = this.props.record.data.destination_duration || 0;
        return Math.max(Math.round(minutes * 60), 1);
    }

    get totalCombinedDuration() {
        return this.routeToUserDuration + this.routeToOriginDuration;
    }
    /* ======================
     * FECHAS
     * ====================== */
    get routeToUserStartDate() {
        return this.props.record.data.on_route_to_user_start_date_widget
            ? new Date(this.props.record.data.on_route_to_user_start_date_widget)
            : null;
    }
    get routeToDestinationDate() {
         return this.props.record.data.on_route_to_destination_start_date_widget
            ? new Date(this.props.record.data.on_route_to_destination_start_date_widget)
            : null;
    }
    get routeToUserEndDate() {
        return this.props.record.data.on_route_to_user_end_date_widget
            ? new Date(this.props.record.data.on_route_to_user_end_date_widget)
            : null;
    }
    get routeToDestinationEndDate() {
        return this.props.record.data.on_route_to_destination_end_date_widget
            ? new Date(this.props.record.data.on_route_to_destination_end_date_widget)
            : null;
    }
    /* ======================
     * TIEMPO TRANSCURRIDO
     * ====================== */
    get elapsedSecondsRouteToUser() {
        const start = this.routeToUserStartDate;
        if (!start) return 0;

        const end = this.routeToUserEndDate;

        if (end) {
            return Math.floor(
                (end.getTime() - start.getTime()) / 1000
            );
        }

        if (this.isRouteToUser) {
            return Math.floor(
                (this.state.now - start.getTime()) / 1000
            );
        }

        return this.routeToUserDuration;
    }

    get elapsedSecondsRouteToOrigin() {
        const start = this.routeToDestinationDate;
        if (!start) return 0;

        const end = this.routeToDestinationEndDate;
        if (end) {
            return Math.max(
                Math.floor((end.getTime() - start.getTime()) / 1000),
                0
            );
        }

        if (this.isRouteToDestination) {
            return Math.max(
                Math.floor((this.state.now - start.getTime()) / 1000),
                0
            );
        }

        return this.routeToOriginDuration;
    }
    /* ======================
     * TIMER ÚNICO (UI)
     * ====================== */
    get currentRouteLabel() {
        if (this.isRouteToUser) return "Ruta al usuario";
        if (this.isRouteToDestination) return "Ruta al destino";
        return "Ruta";
    }
    get currentElapsedSeconds() {
        if (this.isRouteToUser) {
            return this.elapsedSecondsRouteToUser;
        }
        if (this.isRouteToDestination) {
            return this.elapsedSecondsRouteToOrigin;
        }
        return 0;
    }
    get currentRouteDuration() {
        if (this.isRouteToUser) return this.routeToUserDuration;
        if (this.isRouteToDestination) return this.routeToOriginDuration;
        return 0;
    }
    /* ======================
     * BARRA DE PROGRESO
     * ====================== */
    get currentElapsedForBar() {
        if (this.isArrived) {
            return this.routeToUserDuration;
        }

        if (this.isArrived2) {
            return this.totalCombinedDuration;
        }

        if (this.isRouteToUser) {
            return Math.min(this.elapsedSecondsRouteToUser, this.routeToUserDuration);
        }

        if (this.isRouteToDestination) {
            return this.routeToUserDuration + Math.min(
                this.elapsedSecondsRouteToOrigin,
                this.routeToOriginDuration
            );
        }

        return 0;
    }
    get exceededSeconds() {
        const exceeded = this.currentElapsedSeconds - this.currentRouteDuration;
        return exceeded > 0 ? exceeded : 0;
    }

    get formattedExceededTime() {
        if (this.exceededSeconds <= 0) return "";
        return `(+${this.formatTime(this.exceededSeconds)})`;
    }
    get shouldShowProgress() {
        return this.isArrived || this.isArrived2 || this.isRouteToUser || this.isRouteToDestination;
    }
    get progressRatio() {
        if (this.isArrived) {
            return this.dividerPositionRatio;
        }

        if (this.isArrived2) {
            return 1;
        }

        if (!this.isActiveRoute) return 0;

        return Math.min(
            this.currentElapsedForBar / this.totalCombinedDuration,
            1
        );
    }
    get progressPercent() {
        return `${(this.progressRatio * 100).toFixed(1)}%`;
    }

    get service(){
        return this.props.record.data.service_ref
    }
    get truckIconSrc() {
        const service = this.service;
        const ICONS = {
            vial: "/ike_event/static/src/img/ike_icon_truck_blue.png",
            medical: "/ike_event/static/src/img/ike_icon_medical_blue.png",
            home: "/ike_event/static/src/img/ike_icon_home_blue.png",
            legal: "/ike_event/static/src/img/ike_icon_legal_blue.png",
            pets: "/ike_event/static/src/img/ike_icon_pet_blue.png",
        };

        return ICONS[service];
    }
    /* ======================
     * CAMIÓN
     * ====================== */
    get shouldShowTruck() {
        return this.isActiveRoute || this.isArrived || this.isArrived2
    }
    /* ======================
     * MARCADOR DIVISORIO
     * ====================== */
    get dividerPositionRatio() {
        return this.routeToUserDuration / this.totalCombinedDuration;
    }
    get dividerPositionPercent() {
        return `${(this.dividerPositionRatio * 100).toFixed(1)}%`;
    }
    /* ======================
     * FORMATO
     * ====================== */
    formatTime(seconds) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = seconds % 60;

        if (h > 0) {
            return `${h.toString().padStart(2, "0")}:${m
                .toString()
                .padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
        }

        return `${m.toString().padStart(2, "0")}:${s
            .toString()
            .padStart(2, "0")}`;
    }

    get formattedCurrentElapsed() {
        return this.formatTime(this.currentElapsedSeconds);
    }

    get formattedCurrentDuration() {
        return this.formatTime(this.currentRouteDuration);
    }
}

/* ======================
 * REGISTRO
 * ====================== */
registry.category("fields").add("ike_line_progress", {
    component: IkeLineProgress,
});
