/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, useRef, onMounted, useEffect, onWillUnmount } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class IconPickerField extends Component {
    static template = "ike_event.IconPickerField";
    static props = {
        ...standardFieldProps,
        viewType: { type: String },
    };

    setup() {
        this.state = useState({
            isOpen: false,
            searchQuery: "",
            showIconLabel: false,
        });

        this.dropdownRef = useRef("dropdown");

        // Lista de iconos Font Awesome comunes
        this.icons = [
            'fa-address-book', 'fa-address-book-o', 'fa-address-card', 'fa-address-card-o', 'fa-adjust',
            'fa-american-sign-language-interpreting', 'fa-anchor', 'fa-archive', 'fa-area-chart', 'fa-arrows',
            'fa-arrows-h', 'fa-arrows-v', 'fa-arrows-alt', 'fa-assistive-listening-systems', 'fa-asterisk',
            'fa-at', 'fa-audio-description', 'fa-balance-scale', 'fa-ban', 'fa-bar-chart', 'fa-bar-chart-o',
            'fa-barcode', 'fa-bars', 'fa-bath', 'fa-battery-empty', 'fa-battery-full', 'fa-battery-half',
            'fa-battery-quarter', 'fa-battery-three-quarters', 'fa-bed', 'fa-beer', 'fa-bell', 'fa-bell-o',
            'fa-bell-slash', 'fa-bell-slash-o', 'fa-bicycle', 'fa-binoculars', 'fa-birthday-cake', 'fa-blind',
            'fa-bluetooth', 'fa-bluetooth-b', 'fa-bolt', 'fa-bomb', 'fa-book', 'fa-bookmark', 'fa-bookmark-o',
            'fa-braille', 'fa-briefcase', 'fa-bug', 'fa-building', 'fa-building-o', 'fa-bullhorn', 'fa-bullseye',
            'fa-bus', 'fa-calculator', 'fa-calendar', 'fa-calendar-check-o', 'fa-calendar-minus-o', 'fa-calendar-o',
            'fa-calendar-plus-o', 'fa-calendar-times-o', 'fa-camera', 'fa-camera-retro', 'fa-car', 'fa-caret-square-o-down',
            'fa-caret-square-o-left', 'fa-caret-square-o-right', 'fa-caret-square-o-up', 'fa-cart-arrow-down', 'fa-cart-plus',
            'fa-cc', 'fa-certificate', 'fa-check', 'fa-check-circle', 'fa-check-circle-o', 'fa-check-square',
            'fa-check-square-o', 'fa-child', 'fa-circle', 'fa-circle-o', 'fa-circle-o-notch', 'fa-circle-thin',
            'fa-clock-o', 'fa-clone', 'fa-cloud', 'fa-cloud-download', 'fa-cloud-upload', 'fa-code', 'fa-code-fork',
            'fa-coffee', 'fa-cog', 'fa-cogs', 'fa-comment', 'fa-comment-o', 'fa-commenting', 'fa-commenting-o',
            'fa-comments', 'fa-comments-o', 'fa-compass', 'fa-compress', 'fa-copyright', 'fa-creative-commons',
            'fa-credit-card', 'fa-credit-card-alt', 'fa-crop', 'fa-crosshairs', 'fa-cube', 'fa-cubes', 'fa-cutlery',
            'fa-database', 'fa-deaf', 'fa-desktop', 'fa-diamond', 'fa-dot-circle-o', 'fa-download', 'fa-drivers-license-o',
            'fa-eject', 'fa-ellipsis-h', 'fa-ellipsis-v', 'fa-envelope', 'fa-envelope-o', 'fa-envelope-open',
            'fa-envelope-open-o', 'fa-envelope-square', 'fa-eraser', 'fa-exchange', 'fa-exclamation', 'fa-exclamation-circle',
            'fa-exclamation-triangle', 'fa-expand', 'fa-external-link', 'fa-external-link-square', 'fa-eye', 'fa-eye-slash',
            'fa-eyedropper', 'fa-fast-backward', 'fa-fast-forward', 'fa-fax', 'fa-female', 'fa-fighter-jet',
            'fa-file-archive-o', 'fa-file-audio-o', 'fa-file-code-o', 'fa-file-excel-o', 'fa-file-image-o',
            'fa-file-pdf-o', 'fa-file-powerpoint-o', 'fa-file-video-o', 'fa-file-word-o', 'fa-film', 'fa-filter',
            'fa-fire', 'fa-fire-extinguisher', 'fa-flag', 'fa-flag-checkered', 'fa-flag-o', 'fa-flask', 'fa-folder',
            'fa-folder-o', 'fa-folder-open', 'fa-folder-open-o', 'fa-forward', 'fa-frown-o', 'fa-futbol-o',
            'fa-gamepad', 'fa-gavel', 'fa-gift', 'fa-glass', 'fa-globe', 'fa-graduation-cap', 'fa-h-square',
            'fa-hand-lizard-o', 'fa-hand-o-down', 'fa-hand-o-left', 'fa-hand-o-right', 'fa-hand-o-up', 'fa-hand-paper-o',
            'fa-hand-peace-o', 'fa-hand-pointer-o', 'fa-hand-rock-o', 'fa-hand-scissors-o', 'fa-hand-spock-o',
            'fa-handshake-o', 'fa-hashtag', 'fa-hdd-o', 'fa-headphones', 'fa-heart', 'fa-heart-o', 'fa-heartbeat',
            'fa-history', 'fa-home', 'fa-hospital-o', 'fa-hourglass', 'fa-hourglass-end', 'fa-hourglass-half',
            'fa-hourglass-o', 'fa-hourglass-start', 'fa-i-cursor', 'fa-id-badge', 'fa-id-card', 'fa-id-card-o',
            'fa-inbox', 'fa-industry', 'fa-info', 'fa-info-circle', 'fa-key', 'fa-keyboard-o', 'fa-language',
            'fa-laptop', 'fa-leaf', 'fa-lemon-o', 'fa-level-down', 'fa-level-up', 'fa-life-ring', 'fa-lightbulb-o',
            'fa-line-chart', 'fa-location-arrow', 'fa-lock', 'fa-low-vision', 'fa-magic', 'fa-magnet', 'fa-male',
            'fa-map', 'fa-map-marker', 'fa-map-o', 'fa-map-pin', 'fa-map-signs', 'fa-medkit', 'fa-meh-o',
            'fa-microchip', 'fa-microphone', 'fa-microphone-slash', 'fa-minus', 'fa-minus-circle', 'fa-minus-square',
            'fa-minus-square-o', 'fa-mobile', 'fa-money', 'fa-moon-o', 'fa-motorcycle', 'fa-mouse-pointer',
            'fa-music', 'fa-newspaper-o', 'fa-object-group', 'fa-object-ungroup', 'fa-paint-brush', 'fa-paper-plane',
            'fa-paper-plane-o', 'fa-pause', 'fa-pause-circle', 'fa-pause-circle-o', 'fa-paw', 'fa-pencil',
            'fa-pencil-square', 'fa-pencil-square-o', 'fa-percent', 'fa-phone', 'fa-phone-square', 'fa-picture-o',
            'fa-pie-chart', 'fa-plane', 'fa-play', 'fa-play-circle', 'fa-play-circle-o', 'fa-plug', 'fa-plus',
            'fa-plus-circle', 'fa-plus-square', 'fa-plus-square-o', 'fa-podcast', 'fa-power-off', 'fa-print',
            'fa-puzzle-piece', 'fa-qrcode', 'fa-question', 'fa-question-circle', 'fa-question-circle-o', 'fa-quote-left',
            'fa-quote-right', 'fa-random', 'fa-recycle', 'fa-refresh', 'fa-registered', 'fa-reply', 'fa-reply-all',
            'fa-retweet', 'fa-road', 'fa-rocket', 'fa-rss', 'fa-rss-square', 'fa-search', 'fa-search-minus',
            'fa-search-plus', 'fa-server', 'fa-share', 'fa-share-alt', 'fa-share-alt-square', 'fa-share-square',
            'fa-share-square-o', 'fa-shield', 'fa-ship', 'fa-shopping-bag', 'fa-shopping-basket', 'fa-shopping-cart',
            'fa-shower', 'fa-sign-in', 'fa-sign-language', 'fa-sign-out', 'fa-signal', 'fa-sitemap', 'fa-sliders',
            'fa-smile-o', 'fa-snowflake-o', 'fa-sort', 'fa-sort-alpha-asc', 'fa-sort-alpha-desc', 'fa-sort-amount-asc',
            'fa-sort-amount-desc', 'fa-sort-asc', 'fa-sort-desc', 'fa-sort-numeric-asc', 'fa-sort-numeric-desc',
            'fa-space-shuttle', 'fa-spinner', 'fa-spoon', 'fa-square', 'fa-square-o', 'fa-star', 'fa-star-half',
            'fa-star-half-o', 'fa-star-o', 'fa-step-backward', 'fa-step-forward', 'fa-stethoscope', 'fa-sticky-note',
            'fa-sticky-note-o', 'fa-stop', 'fa-stop-circle', 'fa-stop-circle-o', 'fa-street-view', 'fa-suitcase',
            'fa-sun-o', 'fa-tablet', 'fa-tachometer', 'fa-tag', 'fa-tags', 'fa-tasks', 'fa-taxi', 'fa-television',
            'fa-terminal', 'fa-thermometer-empty', 'fa-thermometer-full', 'fa-thermometer-half', 'fa-thermometer-quarter',
            'fa-thermometer-three-quarters', 'fa-thumb-tack', 'fa-thumbs-down', 'fa-thumbs-o-down', 'fa-thumbs-o-up',
            'fa-thumbs-up', 'fa-ticket', 'fa-times', 'fa-times-circle', 'fa-times-circle-o', 'fa-tint', 'fa-toggle-off',
            'fa-toggle-on', 'fa-trademark', 'fa-trash', 'fa-trash-o', 'fa-tree', 'fa-trophy', 'fa-truck', 'fa-tty',
            'fa-umbrella', 'fa-universal-access', 'fa-university', 'fa-unlock', 'fa-unlock-alt', 'fa-upload',
            'fa-user', 'fa-user-circle', 'fa-user-circle-o', 'fa-user-md', 'fa-user-o', 'fa-user-plus',
            'fa-user-secret', 'fa-user-times', 'fa-users', 'fa-video-camera', 'fa-volume-control-phone', 'fa-volume-down',
            'fa-volume-off', 'fa-volume-up', 'fa-wheelchair', 'fa-wheelchair-alt', 'fa-wifi', 'fa-window-close',
            'fa-window-close-o', 'fa-window-maximize', 'fa-window-minimize', 'fa-window-restore', 'fa-wrench',
            'fa-angle-double-down', 'fa-angle-double-left', 'fa-angle-double-right', 'fa-angle-double-up', 'fa-angle-down',
            'fa-angle-left', 'fa-angle-right', 'fa-angle-up', 'fa-arrow-circle-down', 'fa-arrow-circle-left',
            'fa-arrow-circle-o-down', 'fa-arrow-circle-o-left', 'fa-arrow-circle-o-right', 'fa-arrow-circle-o-up',
            'fa-arrow-circle-right', 'fa-arrow-circle-up', 'fa-arrow-down', 'fa-arrow-left', 'fa-arrow-right',
            'fa-arrow-up', 'fa-backward', 'fa-caret-down', 'fa-caret-left', 'fa-caret-right', 'fa-caret-up',
            'fa-chevron-circle-down', 'fa-chevron-circle-left', 'fa-chevron-circle-right', 'fa-chevron-circle-up',
            'fa-chevron-down', 'fa-chevron-left', 'fa-chevron-right', 'fa-chevron-up', 'fa-long-arrow-down',
            'fa-long-arrow-left', 'fa-long-arrow-right', 'fa-long-arrow-up', 'fa-youtube-play', 'fa-ambulance',
            'fa-align-center', 'fa-align-justify', 'fa-align-left', 'fa-align-right', 'fa-bold', 'fa-chain-broken',
            'fa-clipboard', 'fa-columns', 'fa-dedent', 'fa-file', 'fa-file-o', 'fa-file-text', 'fa-file-text-o',
            'fa-files-o', 'fa-floppy-o', 'fa-font', 'fa-header', 'fa-indent', 'fa-italic', 'fa-link', 'fa-list',
            'fa-list-alt', 'fa-list-ol', 'fa-list-ul', 'fa-outdent', 'fa-paperclip', 'fa-paragraph', 'fa-repeat',
            'fa-save', 'fa-scissors', 'fa-strikethrough', 'fa-subscript', 'fa-superscript', 'fa-table', 'fa-text-height',
            'fa-text-width', 'fa-th', 'fa-th-large', 'fa-th-list', 'fa-underline', 'fa-undo'
        ];

        onMounted(() => {
            document.addEventListener('click', this.onClickOutside);
        });

        onWillUnmount(() => {
            document.removeEventListener('click', this.onClickOutside);
        });

        useEffect(
            () => {
                this.checkIfIsCustomIcon();
            },
            () => [this.value]
        );
    }

    get value() {
        return this.props.record.data[this.props.name] || '';
    }

    get filteredIcons() {
        if (!this.state.searchQuery) {
            return this.icons;
        }
        const query = this.state.searchQuery.toLowerCase();
        return this.icons.filter(icon => icon.toLowerCase().includes(query));
    }

    toggleDropdown() {
        this.state.isOpen = !this.state.isOpen;
        if (this.state.isOpen) {
            this.state.searchQuery = "";
        }
    }

    selectIcon(icon) {
        this.props.record.update({ [this.props.name]: icon });
        this.state.isOpen = false;
        this.state.searchQuery = "";
    }

    clearIcon() {
        this.props.record.update({ [this.props.name]: false });
        this.state.isOpen = false;
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }

    addNewIcon() {
        this.state.isOpen = false;
        let newIcon = this.state.searchQuery;
        const splitedNewIcon = newIcon.split(" ");
        if (!splitedNewIcon.includes("fa")) {
            newIcon = "fa " + newIcon;
        }
        this.selectIcon(newIcon);
    }

    checkIfIsCustomIcon() {
        this.state.showIconLabel = false;
        let splittedIcon = this.value.split(" ");
        let self = this;
        let showIconLabel = false;
        for (const value of splittedIcon) {
            if (value.startsWith("fa-") && !self.icons.includes(value)) {
                showIconLabel = true;
                break;
            }
        }
        this.state.showIconLabel = showIconLabel;
    }

    onClickOutside = (ev) => {
        if (this.dropdownRef.el && !this.dropdownRef.el.contains(ev.target)) {
            this.state.isOpen = false;
        }
    }
}

export const iconPickerField = {
    component: IconPickerField,
    supportedTypes: ["char"],
    extractProps: ({ viewType }) => ({
        viewType: viewType,
    }),
    additionalClasses: ["o_icon_picker_field"],
};

registry.category("fields").add("icon_picker", iconPickerField);
