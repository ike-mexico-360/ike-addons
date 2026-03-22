import { rpc } from "@web/core/network/rpc";
import { registry } from "@web/core/registry";

export class GoogleMapService {
    constructor(env, services) {
        this.setup(env, services);
        this.loadPromise = null;
        this.apiKey = null;
        this.isLoaded = false;
    }

    setup(env, services) {
        this.env = env;
        this.orm = services.orm;
    }

    async loadGoogleMaps() {
        // Loaded
        if (this.isLoaded && typeof google !== 'undefined' && google.maps) {
            return Promise.resolve();
        }

        // Current Loading
        if (this.loadPromise) {
            return this.loadPromise;
        }

        // Loaded
        if (typeof google !== 'undefined' && google.maps) {
            this.isLoaded = true;
            return Promise.resolve();
        }

        this.loadPromise = this._loadScript();

        try {
            await this.loadPromise;
            this.isLoaded = true;
        } catch (error) {
            this.loadPromise = null;
            throw error;
        }

        return this.loadPromise;
    }

    async _loadScript() {
        if (!this.apiKey) {
            const google_map_data = await rpc("/ike_event/get_google_map_api_key");
            this.apiKey = google_map_data['api_key'];
        }

        return new Promise((resolve, reject) => {
            window.initGoogleMaps = () => {
                delete window.initGoogleMaps;
                resolve();
            };

            const script = document.createElement('script');
            script.src = `https://maps.googleapis.com/maps/api/js?key=${this.apiKey}`;
            script.src += "&libraries=marker,places";
            script.src += "&callback=initGoogleMaps";
            script.src += "&loading=async";
            script.async = true;
            script.defer = true;
            script.onerror = (error) => {
                delete window.initGoogleMaps;
                reject(new Error('Failed to load Google Maps API', error));
            };

            document.head.appendChild(script);
        });
    }

    isAvailable() {
        return this.isLoaded && typeof google !== 'undefined' && google.maps;
    }

    getApi() {
        return this.isAvailable() ? google.maps : null;
    }

    decodePolyline(encoded) {
        let points = [];
        let index = 0, len = encoded.length;
        let lat = 0, lng = 0;

        while (index < len) {
            let b, shift = 0, result = 0;
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);
            let dLat = (result & 1) ? ~(result >> 1) : (result >> 1);
            lat += dLat;

            shift = 0;
            result = 0;
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);
            let dLng = (result & 1) ? ~(result >> 1) : (result >> 1);
            lng += dLng;

            points.push({ lat: lat / 1e5, lng: lng / 1e5 });
        }

        return points;
    }

    haversineDistance(p1, p2) {
        const R = 6371e3; // meters
        const toRad = deg => deg * (Math.PI / 180);
        const dLat = toRad(p2.lat - p1.lat);
        const dLng = toRad(p2.lng - p1.lng);
        const a =
            Math.sin(dLat / 2) ** 2 +
            Math.cos(toRad(p1.lat)) * Math.cos(toRad(p2.lat)) *
            Math.sin(dLng / 2) ** 2;
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
        return R * c;
    }
}

export const googleMapsService = {
    dependencies: ["orm"],
    start(env, services) {
        return new GoogleMapService(env, services);
    },
};

registry.category("services").add("google_maps_service", googleMapsService);
