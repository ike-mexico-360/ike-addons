/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";
import { deserializeDateTime, formatDateTime } from "@web/core/l10n/dates";

export class ServiceCommentDialog extends Component {
    static template = 'ike_event_portal.ServiceCommentDialog';
    static props = {
        serviceId: { type: Number, required: true },
        close: { type: Function },
        onConfirm: { type: Function, required: true },
        title: { type: String, optional: true },
    };

    static defaultProps = {
        title: _t("Add Comment"),
    };

    translate(str) { return _t(str); }

    setup() {
        this.state = useState({
            comment: '',
            isSubmitting: false,
            error: '',
            comments: [],
            isLoadingComments: true,
            page: 1,
            pageSize: 10,
            total: 0,
        });

        onWillStart(async () => {
            await this.loadComments();
        });
    }

    async loadComments(page = this.state.page) {
        this.state.isLoadingComments = true;
        try {
            const result = await rpc('/provider/portal/services/get_comments', {
                event_supplier_id: this.props.serviceId,
                page,
                page_size: this.state.pageSize,
            });
            this.state.comments = result.success ? result.comments : [];
            if (result.success) {
                this.state.page = result.page;
                this.state.pageSize = result.page_size;
                this.state.total = result.total;
            }
        } catch (error) {
            this.state.comments = [];
        } finally {
            this.state.isLoadingComments = false;
        }
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        return formatDateTime(deserializeDateTime(dateStr), { format: "dd/MM/yyyy HH:mm:ss" });
    }

    onCommentInput(ev) {
        this.state.comment = ev.target.value;
        this.state.error = '';
    }

    get isValid() {
        return !!this.state.comment.trim();
    }

    get pageCount() {
        return Math.max(Math.ceil(this.state.total / this.state.pageSize), 1);
    }

    async previousPage() {
        if (this.state.page > 1 && !this.state.isLoadingComments) {
            await this.loadComments(this.state.page - 1);
        }
    }

    async nextPage() {
        if (this.state.page < this.pageCount && !this.state.isLoadingComments) {
            await this.loadComments(this.state.page + 1);
        }
    }

    closeDialog() {
        this.props.close();
    }

    async confirmComment() {
        const comment = this.state.comment.trim();
        if (!comment) {
            this.state.error = _t("Please write a comment before saving.");
            return false;
        }

        const result = await rpc('/provider/portal/services/add_comment', {
            event_supplier_id: this.props.serviceId,
            comment,
        });

        if (!result.success) {
            this.state.error = result.error || _t("An error occurred while saving the comment.");
            return false;
        }

        return true;
    }

    async SaveComment() {
        this.state.isSubmitting = true;
        try {
            const saved = await this.confirmComment();
            if (saved) {
                this.state.comment = '';
                await this.loadComments(1);
                await this.props.onConfirm();
            }
        } catch (error) {
            this.state.error = error?.data?.message || error.message || _t("An error occurred while saving the comment.");
        } finally {
            this.state.isSubmitting = false;
        }
    }
}
