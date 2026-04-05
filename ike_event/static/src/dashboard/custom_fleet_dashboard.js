import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Layout } from "@web/search/layout";
import { View } from "@web/views/view";

import { Component, onWillStart, onWillUnmount, onMounted, useState, useRef } from '@odoo/owl';


class CustomFleetDashboard extends Component {
    static components = { Layout, View };
    static template = "ike_event.CustomFleetDashboard";
    static props = {
        ...standardActionServiceProps,
    };
    setup() {
        console.log("CustomFleetDashboard setup", this);
        this.googleMapsService = useService("google_maps_service");
        this.orm = this.env.services.orm;
        this.busService = this.env.services.bus_service;

        this.mapRef = useRef("mapContainer");
        this.vehicles = useState([]);
        this.map = null;
        this.intervalId = null;
        this.display = {
            controlPanel: {},
        };
        // Images by color of status
        this.stateIcons = {
            available: "/ike_event/static/src/images/location_point_crane_green.png",
            in_service: "/ike_event/static/src/images/location_point_crane_blue.png",
        };

        onWillStart(() => {
            this.busService.addChannel("custom_fleet_dashboard");
        });

        this.broadcast_update_location = (message) => {
            // message vehicles
            if (message.vehicles && message.vehicles.length > 0) {
                message.vehicles.forEach(updatedVehicle => {
                    // Search for vehicle by array ID
                    const vehicle = this.vehicles.find(v => v.id === updatedVehicle.id);

                    if (vehicle) {
                        const newState = updatedVehicle.x_vehicle_service_state;

                        // Check if vehicle visible on map
                        const visibleVehicle = newState === 'available' || newState === 'in_service';

                        // New position
                        const newPosition = {
                            lat: parseFloat(updatedVehicle.x_latitude),
                            lng: parseFloat(updatedVehicle.x_longitude)
                        };

                        if (!visibleVehicle) {
                            // Remove marker from map if exists
                            if (vehicle.marker) {
                                vehicle.marker.map = null;
                                vehicle.marker = null;
                            }
                            vehicle.x_vehicle_service_state = newState;
                            return;
                        }

                        // Vehicle visible
                        if (!vehicle.marker) {
                            const iconUrl = this.stateIcons[newState] || this.stateIcons["available"];

                            const img = document.createElement("img");
                            img.src = iconUrl;
                            img.style.width = "32px";
                            img.style.height = "32px";

                            vehicle.marker = new google.maps.marker.AdvancedMarkerElement({
                                map: this.map,
                                position: newPosition,
                                content: img,
                                title: vehicle.name,
                            });

                            vehicle.x_vehicle_service_state = newState;
                            vehicle.x_latitude = updatedVehicle.x_latitude;
                            vehicle.x_longitude = updatedVehicle.x_longitude;

                        } else {
                            // Marker exists, check if state changed
                            const stateChanged = vehicle.x_vehicle_service_state !== newState;

                            if (stateChanged) {
                                // Update vehicle state
                                vehicle.x_vehicle_service_state = newState;

                                // old marker
                                vehicle.marker.map = null;

                                // Get new icon URL based on state
                                const iconUrl = this.stateIcons[newState] || this.stateIcons["available"];

                                // Create new image element
                                const img = document.createElement("img");
                                img.src = iconUrl;
                                img.style.width = "32px";
                                img.style.height = "32px";

                                // Create new marker with updated icon and position
                                vehicle.marker = new google.maps.marker.AdvancedMarkerElement({
                                    map: this.map,
                                    position: newPosition,
                                    content: img,
                                    title: vehicle.name,
                                });

                            } else {
                                vehicle.marker.position = newPosition;
                            }

                            // Update vehicle data
                            vehicle.x_latitude = updatedVehicle.x_latitude;
                            vehicle.x_longitude = updatedVehicle.x_longitude;
                        }
                    }
                });
            }
        }

        this.busService.subscribe("update_location_vehicle", this.broadcast_update_location);

        onWillUnmount(() => {
            this.busService.deleteChannel("custom_fleet_dashboard");
            this.busService.unsubscribe("update_location_vehicle", this.broadcast_update_location);
        });

        onMounted(async () => {
            await this.googleMapsService.loadGoogleMaps();

            this.map = new google.maps.Map(this.mapRef.el, {
                zoom: 14,
                center: { lat: 19.4326077, lng: -99.133208 },
                mapId: "FLEET",
            });

            // Vehicles (fleet.vehicle)
            this.vehicles = await this.orm.searchRead(
                "fleet.vehicle",
                [
                    ["active", "=", true],
                    ["disabled", "=", false],
                    ['x_vehicle_service_state', 'in', ['available', 'in_service']],
                    ["x_latitude", "!=", false],
                    ["x_longitude", "!=", false],
                ],
                ["name", "x_latitude", "x_longitude", "x_vehicle_service_state"]
            );

            // Center the map on the markers
            const bounds = new google.maps.LatLngBounds();

            // markers
            for (const vehicle of this.vehicles) {
                if (vehicle.x_latitude && vehicle.x_longitude) {
                    const iconUrl =
                        this.stateIcons[vehicle.x_vehicle_service_state] ||
                        this.stateIcons["disabled"];

                    const img = document.createElement("img");
                    img.src = iconUrl;
                    img.style.width = "32px";
                    img.style.height = "32px";

                    img.onload = () => {
                        const lat = parseFloat(vehicle.x_latitude);
                        const lng = parseFloat(vehicle.x_longitude);

                        if (!isNaN(lat) && !isNaN(lng)) {
                            vehicle.marker = new google.maps.marker.AdvancedMarkerElement({
                                map: this.map,
                                position: { lat, lng },
                                content: img,
                                title: vehicle.name,
                            });

                            // Center and adjust map zoom
                            bounds.extend({ lat, lng });
                            this.map.fitBounds(bounds);
                        }
                    };
                }
            };
            // Update every 5 seconds
            this.intervalId = setInterval(() => {
                this.moveLocationVehiclesInService();
            }, 5000);
        });
    }

    onTestBroadcastClick() {
        const vehicle_ids = []
        for (let i = 0; i < this.vehicles.length; i++) {
            vehicle_ids.push(this.vehicles[i].id);
        }
        this.orm.call('fleet.vehicle', 'move_location_vehicle', [vehicle_ids]);
    }

    moveLocationVehiclesInService() {
        const vehicle_ids = this.vehicles.map(v => v.id);

        if (vehicle_ids.length > 0) {
            this.orm.call('fleet.vehicle', 'move_location_vehicle', [vehicle_ids]);
        }
    }
}


registry.category("lazy_components").add("CustomFleetDashboard", CustomFleetDashboard);
