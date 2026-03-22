/** @odoo-module **/

import { reactive } from "@odoo/owl";

/**
 * Reusable Pagination Service
 *
 * Usage:
 *   import { usePagination } from "@ike_event_portal/components/pagination/pagination_service";
 *
 *   setup() {
 *       this.pagination = usePagination({
 *           pageSize: 10,
 *           getItems: () => this.filteredServices,
 *       });
 *   }
 *
 *   // In template: use this.pagination.paginatedItems, this.pagination.info, etc.
 */

export function usePagination(options = {}) {
    const {
        pageSize = 10,
        getItems = () => [],
    } = options;

    // Create reactive state object with all methods and computed properties
    const pagination = reactive({
        // State
        currentPage: 1,
        pageSize: pageSize,

        // Computed getter for total items
        get totalItems() {
            return getItems().length;
        },

        // Computed getter for total pages
        get totalPages() {
            return Math.ceil(this.totalItems / this.pageSize) || 1;
        },

        // Computed getter for paginated items
        get paginatedItems() {
            const items = getItems();
            const totalPages = this.totalPages;

            // Adjust current page if it exceeds total pages
            if (this.currentPage > totalPages && totalPages > 0) {
                this.currentPage = totalPages;
            }

            const startIndex = (this.currentPage - 1) * this.pageSize;
            const endIndex = startIndex + this.pageSize;

            return items.slice(startIndex, endIndex);
        },

        // Computed getter for pagination info
        get info() {
            const totalItems = this.totalItems;
            const totalPages = this.totalPages;
            const startItem = totalItems === 0 ? 0 : (this.currentPage - 1) * this.pageSize + 1;
            const endItem = Math.min(this.currentPage * this.pageSize, totalItems);

            return {
                startItem,
                endItem,
                totalItems,
                totalPages,
                currentPage: this.currentPage,
                pageSize: this.pageSize,
                hasNextPage: this.currentPage < totalPages,
                hasPrevPage: this.currentPage > 1,
            };
        },

        // Computed getter for visible page numbers
        get visiblePageNumbers() {
            const totalPages = this.totalPages;
            const currentPage = this.currentPage;
            const pages = [];
            const maxVisible = 5;

            if (totalPages <= maxVisible) {
                for (let i = 1; i <= totalPages; i++) {
                    pages.push({ number: i, isEllipsis: false });
                }
            } else {
                // Always show first page
                pages.push({ number: 1, isEllipsis: false });

                if (currentPage > 3) {
                    pages.push({ number: null, isEllipsis: true });
                }

                // Show pages around current page
                const start = Math.max(2, currentPage - 1);
                const end = Math.min(totalPages - 1, currentPage + 1);

                for (let i = start; i <= end; i++) {
                    pages.push({ number: i, isEllipsis: false });
                }

                if (currentPage < totalPages - 2) {
                    pages.push({ number: null, isEllipsis: true });
                }

                // Always show last page
                pages.push({ number: totalPages, isEllipsis: false });
            }

            return pages;
        },

        // Methods
        goToPage(page) {
            const totalPages = this.totalPages;
            if (page >= 1 && page <= totalPages) {
                this.currentPage = page;
            }
        },

        nextPage() {
            if (this.currentPage < this.totalPages) {
                this.currentPage++;
            }
        },

        prevPage() {
            if (this.currentPage > 1) {
                this.currentPage--;
            }
        },

        firstPage() {
            this.currentPage = 1;
        },

        lastPage() {
            this.currentPage = this.totalPages;
        },

        setPageSize(size) {
            this.pageSize = parseInt(size, 10);
            this.currentPage = 1; // Reset to first page
        },

        reset() {
            this.currentPage = 1;
        },
    });

    return pagination;
}