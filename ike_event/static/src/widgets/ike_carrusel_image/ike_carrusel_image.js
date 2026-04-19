/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted, onWillUpdateProps } from "@odoo/owl";

export class IkeCarouselImage extends Component {
    static template = "ike_event.IkeCarouselImage";

    static props = {
        name: String,
        record: Object,
        readonly: { type: Boolean, optional: true },
        id: { type: String, optional: true },
        options: { type: Object, optional: true },
    };

    setup() {
        this.state = useState({
            images: [],
            currentIndex: 0,
            loaded: false,
        });

        this.relationModel =
            this.props.options?.relationModel ||
            this.props.record?.resModel;

        this.imageField =
            this.props.options?.imageField || "file_image";

        onMounted(() => this._loadImages(this.props));

        onWillUpdateProps((nextProps) => {
            this._loadImages(nextProps);
        });
    }


    /**
     * Solo extrae los IDs de los registros del one2many.
     * Nunca toca el binario — la imagen se pide al controlador
     * de forma individual cuando el <img> aparece en el DOM.
     */

    _loadImages(props) {
        const list = props.record?.data?.[props.name];
        console.log("LIST:", list);
        const records = list?.records || [];

        //filtrar nu_evidence
        const nuRecords = records.filter(
            rec => rec.data?.evidence_type === "nu_evidence"
        );

        const images = [];

        nuRecords.forEach((rec) => {
            const details = rec.data?.detail_ids?.records || [];

            details.forEach((detail) => {
                const id = detail.resId;

                const model_detail = detail._config.resModel;

                images.push({
                    id,
                    model: model_detail,
                    evidence_type: rec.data?.evidence_type,
                });
            });
        });

        this.state.images = images;
        this.state.currentIndex = 0;
        this.state.loaded = true;
    }

    /**
     * Reutiliza el controlador nativo de Odoo:
     * GET /web/image/<model>/<id>/<field>
     */
    getImageUrl(img) {
        if (!img?.model || !img?.id) return "";
        return `/web/image/${img.model}/${img.id}/${this.imageField}`;
    }

    getImageLoaded() {
        return "/ike_event/static/description/ike_placeholder.png";
    }

    next() {
        const len = this.state.images.length;
        if (len > 1) {
            this.state.currentIndex = (this.state.currentIndex + 1) % len;
        }
    }

    prev() {
        const len = this.state.images.length;
        if (len > 1) {
            this.state.currentIndex = (this.state.currentIndex - 1 + len) % len;
        }
    }

    get hasMultiple() {
        return this.state.images.length > 1;
    }
}

registry.category("fields").add("ike_carousel_image", {
    component: IkeCarouselImage,
    supportedTypes: ["one2many"],
});