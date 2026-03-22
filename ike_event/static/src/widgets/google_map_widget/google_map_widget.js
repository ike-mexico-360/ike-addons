import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { states_mx } from "./google_map_mx_states";

import { Component, onMounted, onWillRender, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";


export class GoogleMapWidget extends Component {
    static template = "ike_event.GoogleMapWidget";
    static props = {
        ...standardWidgetProps,
        latitude: { type: String, optional: true },
        longitude: { type: String, optional: true },
        country: { type: String, optional: true },
        state: { type: String, optional: true },
        municipality: { type: String, optional: true },
        street: { type: String, optional: true },
        street_number: { type: String, optional: true },
        city: { type: String, optional: true },
        colony: { type: String, optional: true },
        zip_code: { type: String, optional: true },
        location_label: { type: String, optional: true },
        size: { type: String, optional: true },
        showOnLoad: { type: Boolean, optional: true },
    };
    static defaultProps = {
        latitude: "latitude",
        longitude: "longitude",
        size: "500px",
        showOnLoad: true,
    };
    setup() {
        //console.log("GoogleMapWidget", this, this.env.services);
        this.googleMapsService = useService("google_maps_service");
        this.orm = this.env.services.orm;

        this.widgetId = "map_" + parseInt(Math.floor(Math.random() * 10000) + 1);
        this.mapContainer = useRef("mapContainer");
        this.autocompleteCard = useRef("place-autocomplete-card");

        this.map = null;
        this.marker = null;
        this.isUpdating = false;

        this.state = useState({
            mapLoaded: false,
            loadingMap: false,
        });

        if (this.props.showOnLoad) {
            onWillStart(async () => {
                await this.googleMapsService.loadGoogleMaps();
            });
            

            onMounted(() => {
                this.initMap();
                this.state.mapLoaded = true;
            });
        }
        onWillRender(async () => {
            if (!this.map || this.isUpdating) {
                return;
            }

            const currentLat = this.latitude;
            const currentLng = this.longitude;

            if (!currentLat || !currentLng) {
                return;
            }

            const markerLat = this.marker?.position?.lat;
            const markerLng = this.marker?.position?.lng;

            const coordsChanged =
                markerLat !== currentLat ||
                markerLng !== currentLng;

            if (coordsChanged) {
                this.updateMarker(currentLat, currentLng);
                await this.updateData(currentLat, currentLng);
            }
        });
        onWillUnmount(() => {
            if (this.map) {
                this.map = null;
            }
        });
    }

    async loadMap() {
        this.state.loadingMap = true;
        await this.googleMapsService.loadGoogleMaps();
        this.initMap();
        this.state.loadingMap = false;
        this.state.mapLoaded = true;
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

        this.map.addListener('click', async (e) => {
            if (!this.props.readonly) {
                if (this.isUpdating) {
                    return;
                }
                const lat = e.latLng.lat();
                const lng = e.latLng.lng();

                this.updateMarker(lat, lng);
                await this.updateData(lat, lng);
            }
        });

        this.placeAutocomplete = new google.maps.places.PlaceAutocompleteElement();
        this.placeAutocomplete.id = this.widgetId;
        this.placeAutocomplete.locationBias = center;
        this.card = this.autocompleteCard.el;
        this.card.appendChild(this.placeAutocomplete);
        // this.map.controls[google.maps.ControlPosition.TOP_LEFT].push(this.card);

        this.placeAutocomplete.addEventListener('gmp-select', async (response) => {
            // console.log(response);
            const { placePrediction } = response;
            const place = placePrediction.toPlace();
            await place.fetchFields({
                fields: [
                    'displayName',
                    'formattedAddress',
                    'location',
                ]
            });

            if (!this.props.readonly) {
                const lat = place.location.lat();
                const lng = place.location.lng();
                this.updateMarker(lat, lng);
                await this.updateData(lat, lng);
            }
        });

        this.updateMarker(this.latitude, this.longitude);
    }

    updateMarker(lat, lng) {
        // console.log("updateMarker")
        if (!this.map) {
            return;
        }
        if (lat && lng) {
            if (!this.marker) {
                this.createMarker(lat, lng);
            } else {
                this.marker.position = {
                    lat: lat,
                    lng: lng,
                };
            }
            const bounds = this.map.getBounds();
            if (bounds && !bounds.contains(this.marker.position)) {
                this.map.setCenter({ lat, lng });
            }
        } else if (this.marker) {
            google.maps.event.clearInstanceListeners(this.marker);
            this.marker.setMap(null);
            this.marker = null;
        }
    }

    createMarker(lat, lng) {
        this.marker = new google.maps.marker.AdvancedMarkerElement({
            map: this.map,
            gmpDraggable: !this.props.readonly,
            position: {
                lat: lat,
                lng: lng,
            },
        });

        this.marker.addListener('dragend', async (e) => {
            if (!this.props.readonly) {
                const lat = e.latLng.lat();
                const lng = e.latLng.lng();

                await this.updateData(lat, lng);
            }
        });
    }

    async updateData(lat, lng) {
        if (this.isUpdating) {
            return;
        }
        try {
            this.isUpdating = true;

            const geocoder = new google.maps.Geocoder();
            const response = await geocoder.geocode({ location: { lat, lng } });
            //console.log("response", response);
            if (response.results.length) {
                //let result = response.results[0];
                let result = response.results.find(r => r.types.includes("street_address"));
                if (!result) {
                    result = response.results[0];
                }
                const addressComponents = result.address_components;
                let locationData = {
                    formatted_address: result.formatted_address,
                };
                addressComponents.forEach((component) => {
                    const types = component.types;
                    if (types.includes("country")) {
                        locationData.country = component.long_name;
                        locationData.countryCode = component.short_name;
                    }
                    if (types.includes("administrative_area_level_1")) {
                        locationData.state = component.long_name;
                        locationData.stateCode = component.short_name;
                    }
                    if (types.includes("locality")) {
                        locationData.city = component.short_name;
                    }
                    if (types.includes("sublocality")) {
                        locationData.colony = component.short_name;
                    }
                    if (types.includes("postal_code")) {
                        locationData.postalCode = component.short_name;
                    }
                    if (types.includes("street_number")) {
                        locationData.streetNumber = component.short_name;
                    }
                    if (types.includes("route")) {
                        locationData.street = component.long_name;
                    }
                });

                // let municipality_result = response.results.find(r => r.types.includes("administrative_area_level_2"));
                // if (!municipality_result) {
                //     municipality_result = response.results.find(r => r.types.includes("administrative_area_level_3"));
                //      if (municipality_result) {
                //         const municipality = municipality_result.address_components.find(a => a.types.includes("administrative_area_level_3"));
                //         if (municipality) {
                //             locationData.municipality = municipality.short_name;
                //         }
                //     }
                // }
                let municipality_result = response.results.find(r => r.types.includes("administrative_area_level_2"));
                if (!municipality_result) {
                    municipality_result = response.results.find(r => r.types.includes("administrative_area_level_3"));
                }
                if (municipality_result) {
                    const municipality = municipality_result.address_components.find(a => 
                        a.types.includes("administrative_area_level_2") || a.types.includes("administrative_area_level_3")
                    );
                    if (municipality) {
                        locationData.municipality = municipality.short_name;
                    }
                }

                //console.log("locationData", locationData);

                const dataToUpdate = {
                    [this.props.latitude]: lat,
                    [this.props.longitude]: lng,
                };

                if (this.props.location_label) {
                    dataToUpdate[this.props.location_label] = `${locationData.street} <br/> ${locationData.city}, ${locationData.state}, ${locationData.postalCode}`;
                }
                if (this.props.street) dataToUpdate[this.props.street] = locationData.street || '';
                if (this.props.street_number) dataToUpdate[this.props.street_number] = locationData.streetNumber || '';
                if (this.props.city) dataToUpdate[this.props.city] = locationData.city || '';
                if (this.props.colony) dataToUpdate[this.props.colony] = locationData.colony || '';
                if (this.props.zip_code) dataToUpdate[this.props.zip_code] = locationData.postalCode || '';

                let country = null
                // Country
                if (this.props.country && locationData.country) {
                    country = await this.getRecordByCode('res.country', locationData.countryCode, locationData.country, country);
                    if (country) {
                        dataToUpdate[this.props.country] = [country.id, country.display_name]
                    }
                }

                // State
                if (this.props.state && locationData.state) {
                    let stateCode = states_mx[locationData.stateCode] ? states_mx[locationData.stateCode] : locationData.stateCode;
                    let state = await this.getRecordByCode('res.country.state', stateCode, locationData.state, country);
                    if (state) {
                        dataToUpdate[this.props.state] = [state.id, state.display_name]
                    }
                }

                // // Municipality
                // if (this.props.municipality && locationData.municipality) {
                //     if (locationData.municipality) {
                //         const municipality = await this.getRecordByCode('custom.state.municipality', null, locationData.municipality);
                //         // dataToUpdate[this.props.municipality] = [municipality.id, municipality.display_name]
                //         dataToUpdate[this.props.municipality] = municipality.display_name || locationData.municipality;
                //     } else {
                //         dataToUpdate[this.props.municipality] = "";
                //     }
                // }
                  // Municipality
                if (this.props.municipality && locationData.municipality) {
                    const muni = await this.getRecordByZipCode('custom.state.municipality.code', locationData.postalCode);
                    if (muni.id) {
                        dataToUpdate[this.props.municipality] = [muni.id, muni.name];
                    } 
                }

                //console.log("data", dataToUpdate);
                await this.props.record.update(dataToUpdate);
            }
        } catch (err) {
            //console.error("updateData", err);
        } finally {
            this.isUpdating = false;
            if (this.marker && !this.props.readonly) {
                this.marker.gmpDraggable = !this.props.readonly;
            }
        }
    }

    async getRecordByCode(model, code, name, country) {
        if (country) {
            let result = await this.orm.searchRead(
                model,
                [['code', '=', code], ['country_id', '=', country.id]],
                ['id', 'name', 'display_name'],
                { limit: 1 }
            );
            if (result.length) {
                // console.log("record", result[0])
                return result[0];
            }
        }
        if (code) {
            let result = await this.orm.searchRead(
                model,
                [['code', '=', code]],
                ['id', 'name', 'display_name'],
                { limit: 1 }
            );
            if (result.length) {
                // console.log("record", result[0])
                return result[0];
            }
        }
        if (name) {
            let result2 = await this.orm.searchRead(
                model,
                [['name', 'ilike', name]],
                ['id', 'name', 'display_name'],
                { limit: 1 }
            );
            if (result2.length) {
                return result2[0];
            }
        }
        return {};
    }

    async getRecordByZipCode(model, zip_code) {
        if (zip_code) {
            let result = await this.orm.searchRead(
                model,
                [['zip_code', '=', zip_code], ['active', '=', true], ['disabled', '=', false]],
                ['municipality_id'], 
                { limit: 1 }
            );

            if (result.length && result[0].municipality_id) {
                const muniId = Array.isArray(result[0].municipality_id) 
                    ? result[0].municipality_id[0] 
                    : result[0].municipality_id;

                let municipalityResult = await this.orm.searchRead(
                    'custom.state.municipality',
                    [['id', '=', muniId]],
                    ['id', 'name'],
                    { limit: 1 }
                );

                if (municipalityResult.length) {
                    return municipalityResult[0];
                }
            }
        }
        return {};
    }


    get latitude() {
        const val = parseFloat(this.props.record.data[this.props.latitude]);
        return isNaN(val) ? null : val;
    }

    get longitude() {
        const val = parseFloat(this.props.record.data[this.props.longitude]);
        return isNaN(val) ? null : val;
    }
}

export const googleMapWidget = {
    component: GoogleMapWidget,
    extractProps: ({ attrs, options }, dynamicInfo) => {
        // console.log("extractProps", attrs, options, dynamicInfo);
        return {
            latitude: attrs.latitude,
            longitude: attrs.longitude,
            country: attrs.country,
            state: attrs.state,
            municipality: attrs.municipality,
            street: attrs.street,
            street_number: attrs.street_number,
            city: attrs.city,
            colony: attrs.colony,
            zip_code: attrs.zip_code,
            location_label: attrs.location_label,
            size: options.size,
            showOnLoad: options.show_on_load,
        }
    },
};

registry.category("view_widgets").add("google_map_widget", googleMapWidget);
