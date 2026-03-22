import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { darkenHexColor } from "../../services/miscellaneous";

import { Component, onMounted, onWillRender, onWillStart, onWillUnmount, useRef } from "@odoo/owl";


export class GoogleMapRouteWidget extends Component {
    static template = "ike_event.GoogleMapRouteWidget";
    static props = {
        ...standardWidgetProps,
        locations: { type: Object, optional: false },
        size: { type: String, optional: true },
    };
    static defaultProps = {
        size: "500px",
    };
    setup() {
        console.log("GoogleMapRouteWidget", this);
        this.googleMapsService = useService("google_maps_service");

        this.mapContainer = useRef("mapContainer");
        this.map = null;
        this.polylines = [];
        this.markers = [];

        onWillStart(async () => {
            await this.googleMapsService.loadGoogleMaps();
        });

        onWillRender(() => {
            this.drawRoutes();
        });

        onMounted(() => {
            this.initMap();
        });
        onWillUnmount(() => {
            if (this.map) {
                this.map = null;
            }
        });
    }

    async initMap() {
        if (!this.googleMapsService.isAvailable()) {
            console.error("GoogleMapsService");
            return;
        }

        const center = {
            lat: this.latitude || 19.4326077,
            lng: this.longitude || -99.133208,
        };

        this.map = new google.maps.Map(this.mapContainer.el, {
            zoom: 14,
            center: center,
            mapId: "DEMO_TEST",
        });

        this.drawRoutes();
    }

    drawRoutes() {
        if (!this.map) {
            return;
        }

        for (const polyline of this.polylines) {
            polyline.setMap(null);
        }
        for (const polyline of this.markers) {
            polyline.setMap(null);
        }

        this.polylines = [];

        const pathColors = [
            "#06CF9C",
            "#4285F4",
            "#f15c6d",
        ];

        let index = 0;
        for (let point of this.props.locations) {
            const color = pathColors[index % (pathColors.length)];

            // Markers
            const lat = parseFloat(this.props.record.data[`${point}_latitude`]);
            const lng = parseFloat(this.props.record.data[`${point}_longitude`]);
            if (!lat || !lng) {
                continue;
            }
            const pinElement = new google.maps.marker.PinElement({
                scale: 0.75 + (index * 0.35),
                background: pathColors[index % pathColors.length],
                glyphColor: darkenHexColor(color, 30),
                borderColor: darkenHexColor(color, 30),
            });
            let options = {
                map: this.map,
                position: {
                    lat: lat,
                    lng: lng,
                },
                content: pinElement,
            };

            const title = this.props.record.fields[`${point}_label`]?.string;
            if (title) {
                options['title'] = title;
            }
            const marker = new google.maps.marker.AdvancedMarkerElement(options);
            this.markers.push(marker);
            // Route
            const steps = this.props.record.data[`${point}_route`];
            if (steps) {
                const route = [];
                const path = [];
                steps.forEach((step) => {
                    const encoded = step.polyline.encodedPolyline;
                    const decoded = this.googleMapsService.decodePolyline(encoded);
                    path.push(...decoded);
                    route.push({
                        distanceMeters: step.distanceMeters,
                        path: [...decoded],
                    });
                });

                const pathPolyline = new google.maps.Polyline({
                    path: path,
                    map: this.map,
                    strokeColor: color,
                    strokeOpacity: 1.0,
                    strokeWeight: 4,
                });
                this.polylines.push(pathPolyline);
                const bounds = new google.maps.LatLngBounds();
                path.forEach((p) => bounds.extend(p));
                this.map.fitBounds(bounds);
            }
            index++;
        }
    }
}

export const googleMapRouteWidget = {
    component: GoogleMapRouteWidget,
    extractProps: ({ attrs, options }, dynamicInfo) => {
        // console.log("extractProps", attrs, options, dynamicInfo);
        return {
            locations: options.locations,
            size: options.size,
        }
    },
};

registry.category("view_widgets").add("google_map_route_widget", googleMapRouteWidget);
